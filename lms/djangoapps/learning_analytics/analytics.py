
from courseware.grades import iterate_grades_for
from courseware.models import StudentModule
from data import *
from datetime import timedelta
from django.contrib.auth.models import User
from models import SortGrades, CourseTime, CourseStruct, StudentGrades, CourseAccesses
from student.models import CourseEnrollment
from django.db.models import Q

import copy
import datetime
import ast


INACTIVITY_TIME = 600  # Time considered inactivity


##########################################################################
######################## COURSE STRUCT ###################################
##########################################################################

def update_DB_course_struct(course_key):
    """
    Saves course structure to database
    """
    # Get course
    course = get_course_module(course_key)
    # Create return structure
    course_struct = get_course_struct(course)
    
    chapters_sql = CourseStruct.objects.filter(course_id=course_key, section_type='chapter')
    sequentials_sql = CourseStruct.objects.filter(course_id=course_key, section_type='sequential')
    verticals_sql = CourseStruct.objects.filter(course_id=course_key, section_type='vertical')
    
    chapter_index = 1
    for chapter in course_struct['chapters']:
        if (chapters_sql.filter(module_state_key=chapter['id']).count() == 0):
            # Create entry
            CourseStruct.objects.create(course_id=course_key,
                                      module_state_key=chapter['id'],
                                      name=chapter['name'],
                                      section_type='chapter',
                                      graded=chapter['graded'],
                                      released=chapter['released'],
                                      index=chapter_index)
        else:
            # Update entry
            chapters_sql.filter(module_state_key=chapter['id']).update(name=chapter['name'],
                                                                       section_type='chapter',
                                                                       graded=chapter['graded'],
                                                                       released=chapter['released'],
                                                                       index=chapter_index)
        # Sequentials
        seq_index = 1
        chapt_seq_sql = sequentials_sql.filter(father=chapters_sql.get(module_state_key=chapter['id']))
        for sequential in chapter['sequentials']:
            if(chapt_seq_sql.filter(module_state_key=sequential['id']).count() == 0):
                # Create entry
                CourseStruct.objects.create(course_id=course_key,
                                            module_state_key=sequential['id'],
                                            name=sequential['name'],
                                            section_type='sequential',
                                            father=chapters_sql.get(module_state_key=chapter['id']),
                                            graded=sequential['graded'],
                                            released=sequential['released'],
                                            index=seq_index)
            else:
                # Update entry
                chapt_seq_sql.filter(module_state_key=sequential['id']).update(name=sequential['name'],
                                                                               section_type='sequential',
                                                                               graded=sequential['graded'],
                                                                               released=sequential['released'],
                                                                               index=seq_index)
            seq_index = seq_index + 1
            
            # Verticals
            vert_index = 1
            seq_vert_sql = verticals_sql.filter(father=sequentials_sql.get(module_state_key=sequential['id']))
            for vertical in sequential['verticals']:
                if(seq_vert_sql.filter(module_state_key=vertical['id']).count() == 0):
                    # Create entry
                    CourseStruct.objects.create(course_id=course_key,
                                                module_state_key=vertical['id'],
                                                name=vertical['name'],
                                                section_type='vertical',
                                                father=sequentials_sql.get(module_state_key=sequential['id']),
                                                graded=vertical['graded'],
                                                released=vertical['released'],
                                                index=vert_index)
                else:
                    # Update entry
                    seq_vert_sql.filter(module_state_key=vertical['id']).update(name=vertical['name'],
                                                                                section_type='vertical',
                                                                                graded=vertical['graded'],
                                                                                released=vertical['released'],
                                                                                index=vert_index)
                vert_index = vert_index + 1
        chapter_index = chapter_index + 1
    
    
def get_DB_course_struct(course_key, include_verticals=False, include_unreleased=True):
    """
    Gets course structure from database
    
    course_key: course locator
    include_verticals: if true, the result will include verticals
    incluse_unreleased: if true, the result will include unreleased sections
    """
    # Course struct
    course_struct = []
    if include_unreleased:
        sql_struct = CourseStruct.objects.filter(course_id=course_key)
    else:
        sql_struct = CourseStruct.objects.filter(course_id=course_key, released=True)
    
    num_ch = sql_struct.filter(section_type='chapter').count()
    for i in range(1, num_ch + 1):
        chapt = sql_struct.filter(section_type='chapter', index=i)
        if chapt.count() != 0:
            chapt = chapt[0]
        else:
            return None
        
        ch_cont = {'id': chapt.id,
                   'module_id': chapt.module_state_key,
                   'name': chapt.name,
                   'graded': chapt.graded,
                   'type': 'chapter',
                   'sequentials': []}
        
        num_seqs = sql_struct.filter(section_type='sequential', father_id=chapt.id).count()
        for j in range(1, num_seqs + 1):
            seq = sql_struct.filter(section_type='sequential', father_id=chapt.id, index=j)
            if seq.count() != 0:
                seq = seq[0]
            else:
                return None
            
            if include_verticals:
                seq_cont = {'id': seq.id,
                            'module_id': seq.module_state_key,
                            'name': seq.name,
                            'graded': seq.graded,
                            'type': 'sequential',
                            'verticals': []}
                num_verts = sql_struct.filter(section_type='vertical', father_id=seq.id).count()
                for k in range(1, num_verts + 1):
                    vert = sql_struct.filter(section_type='vertical', father_id=seq.id, index=k)
                    if vert.count() != 0:
                        vert = vert[0]
                    else:
                        return None
                    seq_cont['verticals'].append({'id': vert.id,
                                                  'module_id': vert.module_state_key,
                                                  'name': vert.name,
                                                  'graded': vert.graded,
                                                  'type': 'vertical'})
                ch_cont['sequentials'].append(seq_cont)
            else:
                ch_cont['sequentials'].append({'id': seq.id,
                                               'module_id': seq.module_state_key,
                                               'name': seq.name,
                                               'graded': seq.graded,
                                               'type': 'sequential'})
        course_struct.append(ch_cont)
    return course_struct


#################################################################################
######################## SORT COURSE STUDENTS VISUALIZATION #####################
#################################################################################

def sort_course_homework(course_key):
    """
    Sort number of students that haven't done, have fail, have done ok, or
    have done very good each homework of a given course
    """
    
    course = get_course_module(course_key)
    
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit

    # Obtain all sections with their released problems from grading_context
    full_gc = dump_full_grading_context(course)
    
    # Fill sort_homework
    sort_homework = {'graded_sections':[],
                     'weight_subsections':[]}
    
    for section in full_gc['graded_sections']:
        if section['released']:
            sort_homework['graded_sections'].append({'category': section['category'], 'label': section['label'],
                                                     'name': section['name'], 'NOT': 0, 'FAIL': 0,
                                                     'OK': 0, 'PROFICIENCY': 0})
    
    for subsection in full_gc['weight_subsections']:
        for grad_section in sort_homework['graded_sections']:
            if grad_section['category'] == subsection['category']:
                sort_homework['weight_subsections'].append({'category': subsection['category'], 'NOT': 0,
                                                            'FAIL': 0, 'OK': 0, 'PROFICIENCY': 0})
                break
            
    sort_homework['weight_subsections'].append({'category': 'Total', 'NOT': 0,
                                                'FAIL': 0, 'OK': 0, 'PROFICIENCY': 0})
    

    student_grades = (StudentGrades.objects.filter(course_id=course_key)
                      .filter(~Q(student_id=StudentGrades.ALL_STUDENTS))
                      .filter(~Q(student_id=StudentGrades.PROF_GROUP))
                      .filter(~Q(student_id=StudentGrades.PASS_GROUP))
                      .filter(~Q(student_id=StudentGrades.FAIL_GROUP)))    
                           
    for student_grade in student_grades:
        grades = ast.literal_eval(student_grade.grades)
        
        for i in range(len(grades['graded_sections'])):
            if grades['graded_sections'][i]['done'] and grades['graded_sections'][i]['total'] > 0:
                percent = grades['graded_sections'][i]['score'] / grades['graded_sections'][i]['total']
                if percent >= proficiency_limit:
                    sort_homework['graded_sections'][i]['PROFICIENCY'] += 1
                elif percent >= pass_limit:
                    sort_homework['graded_sections'][i]['OK'] += 1
                else:
                    sort_homework['graded_sections'][i]['FAIL'] += 1
            else:
                sort_homework['graded_sections'][i]['NOT'] += 1
        
        for j in range(len(grades['weight_subsections'])):
            if grades['weight_subsections'][j]['done'] and grades['weight_subsections'][j]['total'] > 0:
                percent = grades['weight_subsections'][j]['score'] / grades['weight_subsections'][j]['total']
                if percent >= proficiency_limit:
                    sort_homework['weight_subsections'][j]['PROFICIENCY'] += 1
                elif percent >= pass_limit:
                    sort_homework['weight_subsections'][j]['OK'] += 1
                else:
                    sort_homework['weight_subsections'][j]['FAIL'] += 1
            else:
                sort_homework['weight_subsections'][j]['NOT'] += 1
        
    return sort_homework


def update_DB_sort_course_homework(course_key):
    """
    Recalculate sort course homework data and update SQL table
    """
            
    sort_homework = sort_course_homework(course_key)
    
    #### Weight sections ####
    ws_sql = SortGrades.objects.filter(course_id=course_key, sort_type='WS')
    # Delete old data
    if ws_sql.count() > 0:
        for entry in ws_sql:
            exists = False
            for subsection in sort_homework['weight_subsections']:
                if subsection['category'] == entry.label:
                    exists = True
                    break 
            if not exists:
                # Delete old entry
                entry.delete()
                
    # Add data
    for subsection in sort_homework['weight_subsections']:
        
        if (ws_sql.count() == 0 or 
               ws_sql.filter(label=subsection['category']).count() == 0):
            # Create entry
            SortGrades.objects.create(course_id=course_key,
                                      sort_type='WS',
                                      label=subsection['category'],
                                      category=subsection['category'],
                                      name=subsection['category'],
                                      num_not=subsection['NOT'],
                                      num_fail=subsection['FAIL'],
                                      num_pass=subsection['OK'],
                                      num_prof=subsection['PROFICIENCY']
                                      )
        else:
            # Update entry
            entry = ws_sql.filter(label=subsection['category']);
            entry.update(sort_type='WS',
                         label=subsection['category'],
                         category=subsection['category'],
                         name=subsection['category'],
                         num_not=subsection['NOT'],
                         num_fail=subsection['FAIL'],
                         num_pass=subsection['OK'],
                         num_prof=subsection['PROFICIENCY'])
            for e in entry:
                e.save()
    
    #### Graded sections ####
    gs_sql = SortGrades.objects.filter(course_id=course_key, sort_type='GS')
    # Delete old data
    if gs_sql.count() > 0:
        for entry in gs_sql:
            exists = False
            for section in sort_homework['graded_sections']:
                if section['label'] == entry.label:
                    exists = True
                    break 
            if not exists:
                # Delete old entry
                entry.delete()
                
    # Add data
    for section in sort_homework['graded_sections']:
        
        if (gs_sql.count() == 0 or 
               gs_sql.filter(label=section['label']).count() == 0):
            # Create entry
            SortGrades.objects.create(course_id=course_key,
                                      sort_type='GS',
                                      label=section['label'],
                                      category=section['category'],
                                      name=section['name'],
                                      num_not=section['NOT'],
                                      num_fail=section['FAIL'],
                                      num_pass=section['OK'],
                                      num_prof=section['PROFICIENCY'])
        else:
            # Update entry
            entry = gs_sql.filter(label=section['label']);
            entry.update(sort_type='GS',
                         label=section['label'],
                         category=section['category'],
                         name=section['name'],
                         num_not=section['NOT'],
                         num_fail=section['FAIL'],
                         num_pass=section['OK'],
                         num_prof=section['PROFICIENCY'])
            for e in entry:
                e.save()
    

def get_DB_sort_course_homework(course_key):
    """
    Returns sort_course_homework from database
    """
    
    ws_sql = SortGrades.objects.filter(course_id=course_key, sort_type='WS')
    gs_sql = SortGrades.objects.filter(course_id=course_key, sort_type='GS')
    
    sort_homework = {'graded_sections':[],
                     'weight_subsections':[]}
    # Weighted subsections
    for entry in ws_sql:
        sort_homework['weight_subsections'].append({'category': entry.category, 'NOT': entry.num_not,
                                                    'FAIL': entry.num_fail,
                                                    'OK': entry.num_pass,
                                                    'PROFICIENCY': entry.num_prof})
    
    # Graded sections
    for entry in gs_sql:
        sort_homework['graded_sections'].append({'category': entry.category, 'label': entry.label,
                                                 'name': entry.name, 'NOT': entry.num_not,
                                                 'FAIL': entry.num_pass,
                                                 'OK': entry.num_pass,
                                                 'PROFICIENCY': entry.num_prof})
        
    return sort_homework
        
        
###################################################################
############### STUDENTS GRADES VISUALIZATION #####################
###################################################################

def get_student_grades(course_key, student, full_gc=None, sort_homework=None, weight_data=None):
    """
    Get student grades for given student and course
    """
    
    if full_gc is None:
        full_gc = dump_full_grading_context(get_course_module(course_key))
        
    if (sort_homework is None or weight_data is None):
        sort_homework, weight_data = get_student_grades_course_struct(full_gc)

    # Sort each homework into its category
    i = 0
    for section in full_gc['graded_sections']:
        if section['released']:
            total_grade = 0
            done = False
            for problem in section['problems']:
                grade = get_problem_score(course_key, student, problem)[0]  # Get only grade
                if grade is not None:
                    total_grade += grade
                    done = True
                 
            if done:
                # Add grade to weight subsection
                if weight_data[section['category']]['score'] is None:
                    weight_data[section['category']]['score'] = total_grade
                else:
                    weight_data[section['category']]['score'] += total_grade
                         
                sort_homework['graded_sections'][i]['score'] = total_grade
            else:
                sort_homework['graded_sections'][i]['done'] = False
            i += 1
             
    # Sort grades for weight subsections
    total_score = 0
    total_weight = 0
    for subsection in sort_homework['weight_subsections']:
        if weight_data[subsection['category']]['score'] is None:
            subsection['done'] = False
        subsection['total'] = weight_data[subsection['category']]['total']
        subsection['score'] = weight_data[subsection['category']]['score']
        
        if subsection['score'] is not None:
            total_score += (subsection['score'] / subsection['total']) * subsection['weight']
        
        total_weight += subsection['weight']
        # Clean score
        weight_data[subsection['category']]['score'] = None
        
    sort_homework['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': total_weight,
                                                'score': total_score,
                                                'done': True })
 
    return sort_homework
    
def get_student_grades_course_struct(full_gc):
    """
    Returns course structure to fill in with student grades
    """
    # Fill sort_homework
    sort_homework = {'graded_sections':[],
                     'weight_subsections':[]}
    weight_data = {}
    index = 0
    for subsection in full_gc['weight_subsections']:
        for grad_section in full_gc['graded_sections']:
            if grad_section['released'] and grad_section['category'] == subsection['category']:
                sort_homework['weight_subsections'].append({'category': subsection['category'],
                                                            'weight': subsection['weight'],
                                                            'total': 0,
                                                            'score': None,
                                                            'done': True})
                weight_data[subsection['category']] = {'index': index, 'score': None, 'total': 0,
                                                       'weight': subsection['weight']}
                index += 1
                break
         
    for section in full_gc['graded_sections']:
        if section['released']:
            sort_homework['graded_sections'].append({'category': section['category'],
                                                     'label': section['label'],
                                                     'name': section['name'],
                                                     'total': section['max_grade'],
                                                     'score': None,
                                                     'done': True })
            # Add total released
            weight_data[section['category']]['total'] += section['max_grade']
     
    return sort_homework, weight_data


def update_DB_student_grades(course_key):
    """
    Update students grades for given course
    """
    # Update student grade
    course = get_course_module(course_key)
    students = get_course_students(course_key)
    full_gc = dump_full_grading_context(course)
    sort_homework_std, weight_data_std = get_student_grades_course_struct(full_gc)
    
    all_std_grades = copy.deepcopy(sort_homework_std)
    all_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1,
                                                'score': 0,
                                                'done': True })
    prof_std_grades = copy.deepcopy(sort_homework_std)
    prof_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1,
                                                'score': 0,
                                                'done': True })
    pass_std_grades = copy.deepcopy(sort_homework_std)
    pass_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1,
                                                'score': 0,
                                                'done': True })
    fail_std_grades = copy.deepcopy(sort_homework_std)
    fail_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1,
                                                'score': 0,
                                                'done': True })
    all_count = 0
    prof_count = 0
    pass_count = 0
    fail_count = 0
    
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit
    
    ## TODO CHAPUZA!!!
    total_aux = 0
    
    for student in students:
        std_grades = get_student_grades(course_key, student, full_gc,
                                        copy.deepcopy(sort_homework_std),
                                        copy.deepcopy(weight_data_std))
        
        ## TODO CHAPUZA!!
        total_aux = std_grades['weight_subsections'][-1]['total']
        
        # get grade group
        total_grade = std_grades['weight_subsections'][-1]['score']/std_grades['weight_subsections'][-1]['total']
        if total_grade >= proficiency_limit:
            grade_type = 'PROF'
        elif total_grade >= pass_limit:
            grade_type = 'OK'
        else:
            grade_type = 'FAIL'
            
        exists = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
        if exists.count() > 0:
            exists.update(grades=std_grades, grade_group=grade_type, last_calc=datetime.datetime.now())
        else:
            StudentGrades.objects.create(course_id=course_key,
                                         student_id=student.id,
                                         grades=std_grades,
                                         grade_group=grade_type)
        
        # Add grade to groups
        # All
        all_std_grades = add_students_grades(all_std_grades, std_grades)
        all_count += 1
        # Group
        if grade_type == 'PROF':
            prof_std_grades = add_students_grades(prof_std_grades, std_grades)
            prof_count += 1
        elif grade_type == 'OK':
            pass_std_grades = add_students_grades(pass_std_grades, std_grades)
            pass_count += 1
        else:
            fail_std_grades = add_students_grades(fail_std_grades, std_grades)
            fail_count += 1
    
    ## TODO CHAPUZAA!!! 
    all_std_grades['weight_subsections'][-1]['total'] = total_aux
    prof_std_grades['weight_subsections'][-1]['total'] = total_aux
    pass_std_grades['weight_subsections'][-1]['total'] = total_aux
    fail_std_grades['weight_subsections'][-1]['total'] = total_aux
    
    # Process mean grade
    all_std_grades = mean_student_grades(all_std_grades, all_count)
    prof_std_grades = mean_student_grades(prof_std_grades, prof_count)
    pass_std_grades = mean_student_grades(pass_std_grades, pass_count)
    fail_std_grades = mean_student_grades(fail_std_grades, fail_count)
    
    # Get all grade_type
    percent = all_std_grades['weight_subsections'][-1]['score']/all_std_grades['weight_subsections'][-1]['total']
    if percent >= proficiency_limit:
        all_grade_type = 'PROF'
    elif percent >= pass_limit:
        all_grade_type = 'OK'
    else:
        all_grade_type = 'FAIL'
    
    # Add groups to DB
    # All
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.ALL_STUDENTS)
    if exists.count() > 0:
        exists.update(grades=all_std_grades, grade_group=all_grade_type, last_calc=datetime.datetime.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.ALL_STUDENTS,
                                     grades=all_std_grades,
                                     grade_group=all_grade_type)
    # Proficiency
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.PROF_GROUP)
    if exists.count() > 0:
        exists.update(grades=prof_std_grades, grade_group='PROF', last_calc=datetime.datetime.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.PROF_GROUP,
                                     grades=prof_std_grades,
                                     grade_group='PROF')
    # Pass
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.PASS_GROUP)
    if exists.count() > 0:
        exists.update(grades=pass_std_grades, grade_group='OK', last_calc=datetime.datetime.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.PASS_GROUP,
                                     grades=pass_std_grades,
                                     grade_group='OK')
    # Fail
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.FAIL_GROUP)
    if exists.count() > 0:
        exists.update(grades=fail_std_grades, grade_group='FAIL', last_calc=datetime.datetime.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.FAIL_GROUP,
                                     grades=fail_std_grades,
                                     grade_group='FAIL')
        
            
def add_students_grades(original, new):
    """
    Add grades from 2 different students
    """
    for i in range(len(original['graded_sections'])):
        if new['graded_sections'][i]['score'] is not None:
            if original['graded_sections'][i]['score'] is None:
                original['graded_sections'][i]['score'] = new['graded_sections'][i]['score']
            else:
                original['graded_sections'][i]['score'] += new['graded_sections'][i]['score']
    
    for j in range(len(original['weight_subsections'])):
        if original['weight_subsections'][j]['total'] == 0:
            original['weight_subsections'][j]['total'] = new['weight_subsections'][j]['total']
            
        if new['weight_subsections'][j]['score'] is not None:
            if original['weight_subsections'][j]['score'] is None:
                original['weight_subsections'][j]['score'] = new['weight_subsections'][j]['score']
            else:
                original['weight_subsections'][j]['score'] += new['weight_subsections'][j]['score']
    
    return original


def mean_student_grades(std_grade, number):
    """
    Calculate mean grade for a structure with grades of different students
    """
    if number > 1:
        for section in std_grade['graded_sections']:
            if section['score'] is not None:
                section['score'] = section['score'] / number
        
        for section in std_grade['weight_subsections']:
            if section['score'] is not None:
                section['score'] = section['score'] / number
        
    return std_grade


def get_DB_student_grades(course_key, student_id=None):
    """
    Return students grades from database
    
    course_key: course id key
    student: if None, function will return all students
    """
    
    # Students grades
    students_grades = {}
    if student_id is None:
        sql_grades = StudentGrades.objects.filter(course_id=course_key)
    else:
        sql_grades = StudentGrades.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_grade in sql_grades:
        students_grades[std_grade.student_id] = ast.literal_eval(std_grade.grades)
        
    return students_grades 


###################################################################     
################### TIME SPENT VISUALIZATION ######################
###################################################################

def create_time_chapters(course_key):
    """
    Creates an array of chapters with times for each one
    """
    
    time_chapters = {}
    
    chapters = CourseStruct.objects.filter(course_id=course_key, section_type='chapter')
    
    for chapter in chapters:
        chapter_elem = {'time_spent': 0,
                        'sequentials': {}}
        sequentials = CourseStruct.objects.filter(course_id=course_key, section_type='sequential', father=chapter)
        for seq in sequentials:
            chapter_elem['sequentials'][seq.id] = {'time_spent': 0}
        time_chapters[chapter.id] = chapter_elem
   
    return time_chapters


def get_student_spent_time(course_key, student, time_chapters=None, course_blocks=None):
    """
    Add student spent time in course in each chapter to a given
    dictionary with times for each section.
    
    course_key: Course opaque key
    student_id: Student ID
    time_chapters: Array with times for each section to fill. If argument
                   not given, create a new array
    course_blocks: Dictionary with all course xblocks ids. If argument not
                   given, create a new dictionary
    """
    
    # Create time chapters & course_blocks if not given
    if time_chapters is None:
        time_chapters = create_time_chapters(course_key)
    if course_blocks is None:
        course_blocks = get_course_blocks(get_course_module(course_key))
    
    # Get events
    time_data = {'current_chapter': None, 'current_seq': None,
                 'initial_time': None, 'last_time': None}
 
    events = get_course_events_sql(course_key, student.username)

    for event in events:
        if event.event_source == 'server':
            time_data, time_chapters = manage_server_event(time_data, time_chapters, event, course_blocks)
        elif event.event_source == 'browser':
            time_data, time_chapters = manage_browser_event(time_data, time_chapters, event)   
            
    # Close in case user is still browsing
    time_data, time_chapters = activity_close(time_chapters,
                                              time_data,
                                              datetime.datetime.utcnow())
    
    return time_chapters


def manage_browser_event(time_data, time_chapters, event):
    # Get event location
    course_key, chapt_key, seq_key = get_locations_from_url(event.page)
    if event.event_type == 'page_close':
        if (time_data['current_chapter'] != None and 
            time_data['current_chapter'] == chapt_key and 
            time_data['current_seq'] == seq_key):
            # Close activity
            time_data, time_chapters = activity_close(time_chapters, time_data, event.dtcreated)
    else:      
        if time_data['current_chapter'] == None:
            # Start activity
            time_data['current_chapter'] = chapt_key
            time_data['current_seq'] = seq_key
            time_data['initial_time'] = event.dtcreated
            time_data['last_time'] = event.dtcreated
        else:
            if (time_data['current_chapter'] == chapt_key and
                time_data['current_seq'] == seq_key):
                # Same sequence and chapter -> Update activity
                time_data, time_chapters = activity_update(time_chapters,
                                                           time_data,
                                                           event.dtcreated)
            else:
                # Sequence changed -> Close activity with new seq
                time_data, time_chapters = activity_close(time_chapters,
                                                          time_data,
                                                          event.dtcreated,
                                                          chapt_key, seq_key)
                
    return  (time_data, time_chapters)


def manage_server_event(time_data, time_chapters, event, course_blocks=None):
    # Get event location
    course_key, chapt_key, seq_key = get_locations_from_url(event.event_type, course_blocks)
   
    if ((course_key == None) or
        (chapt_key == None and 
        seq_key == None)):
        # logout / dashboard / load courseware,info, xblock etc -> Close activity
        if time_data['current_chapter'] != None:
            # Close activity
            time_data, time_chapters = activity_close(time_chapters, time_data, event.dtcreated)
    else:
        if time_data['current_chapter'] == None:
            # Start activity
            time_data['current_chapter'] = chapt_key
            time_data['current_seq'] = seq_key
            time_data['initial_time'] = event.dtcreated
            time_data['last_time'] = event.dtcreated
        else:
            if (time_data['current_chapter'] == chapt_key and 
                time_data['current_seq'] == seq_key):
                # Same chapter and seq -> Update activity
                time_data, time_chapters = activity_update(time_chapters,
                                                           time_data,
                                                           event.dtcreated)
            else:
                # Sequential or chapter close -> Close activity with new chapter
                time_data, time_chapters = activity_close(time_chapters,
                                                          time_data,
                                                          event.dtcreated,
                                                          chapt_key,
                                                          seq_key)
           
    return (time_data, time_chapters)
    

def activity_close(time_chapters, time_data, current_time, new_chapter=None, new_seq=None):
    # If activity already closed
    if (time_data['last_time'] is None or
        time_data['initial_time'] is None or
        time_data['current_chapter'] is None):
        return (time_data, time_chapters)
    
    # Add activity time
    time = time_data['last_time'] - time_data['initial_time']
    elapsed_time = current_time - time_data['last_time']
    
    if (elapsed_time.days != 0 or 
        elapsed_time.seconds > INACTIVITY_TIME):
        elapsed_time = timedelta(seconds=INACTIVITY_TIME)
        
    time_chapters = add_course_time(time_data['current_chapter'],
                                    time_data['current_seq'],
                                    time + elapsed_time, time_chapters)
    
    if new_seq == None and new_chapter == None:
        # Stop activity
        time_data['current_chapter'] = None
        time_data['current_seq'] = None
        time_data['initial_time'] = None
        time_data['last_time'] = None
    else:
        time_data['current_chapter'] = new_chapter
        time_data['current_seq'] = new_seq
        time_data['initial_time'] = current_time
        time_data['last_time'] = current_time
    
    return (time_data, time_chapters)


def activity_update(time_chapters, time_data, current_time):
    # If activity is closed
    if (time_data['last_time'] is None or
        time_data['initial_time'] is None or
        time_data['current_chapter'] is None):
        return (time_data, time_chapters)
    
    # Update activity
    elapsed_time = current_time - time_data['last_time']
    if (elapsed_time.days != 0 or 
        elapsed_time.seconds > INACTIVITY_TIME):
        # Inactivity
        time = time_data['last_time'] - time_data['initial_time']
        time = time + timedelta(seconds=INACTIVITY_TIME)  # Add inactivity time
        time_chapters = add_course_time(time_data['current_chapter'],
                                        time_data['current_seq'],
                                        time, time_chapters)
        time_data['initial_time'] = current_time
        time_data['last_time'] = current_time
    else:
        # Update activity
        time_data['last_time'] = current_time  
            
    return (time_data, time_chapters)
    
    
def add_course_time(chapter_key, sequential_key, time, time_chapters):
    time_spent = time.seconds + time.days * 3600 * 24
    for chapter_id in time_chapters.keys():
        if (CourseStruct.objects.filter(pk=chapter_id)[0] != None and
            compare_locations(CourseStruct.objects.filter(pk=chapter_id)[0].module_state_key, chapter_key)):
            # Add chapter time
            time_chapters[chapter_id]['time_spent'] = time_chapters[chapter_id]['time_spent'] + time_spent
            if sequential_key != None:
                for sequential_id in time_chapters[chapter_id]['sequentials'].keys():
                    if (CourseStruct.objects.filter(pk=sequential_id)[0] != None and
                        compare_locations(CourseStruct.objects.filter(pk=sequential_id)[0].module_state_key, sequential_key)):
                        # Add sequential time
                        (time_chapters[chapter_id]['sequentials'][sequential_id]['time_spent']) = (time_chapters[chapter_id]['sequentials'][sequential_id]['time_spent'] + time_spent)
    return time_chapters


def add_time_chapter_time(original, new):
    """
    Add time in chapter_time new to chapter_time original
    """
    if original.keys() != new.keys():
        # # TODO exception
        return
    
    for ch_id in original.keys():
        original[ch_id]['time_spent'] = original[ch_id]['time_spent'] + new[ch_id]['time_spent']
        if original[ch_id]['sequentials'].keys() != new[ch_id]['sequentials'].keys():
            # # TODO exception
            return
        for seq_id in original[ch_id]['sequentials'].keys():
            original[ch_id]['sequentials'][seq_id]['time_spent'] = (original[ch_id]['sequentials'][seq_id]['time_spent'] + 
                                                           new[ch_id]['sequentials'][seq_id]['time_spent'])

    return original


def update_DB_course_spent_time(course_key):
    """
    Recalculate course spent time and update data in database
    """
    
    time_chapters = create_time_chapters(course_key)
    # Student groups time chapters
    time_chapters_all = copy.deepcopy(time_chapters)
    time_chapters_prof = copy.deepcopy(time_chapters)
    time_chapters_ok = copy.deepcopy(time_chapters)
    time_chapters_fail = copy.deepcopy(time_chapters)
    
    students = get_course_students(course_key)
    
    course_blocks = get_course_blocks(get_course_module(course_key))
    
    # Add students time chapters to database
    for student in students:
        time_chapters_student = copy.deepcopy(time_chapters)
        time_chapters_student = get_student_spent_time(course_key,
                                                       student,
                                                       time_chapters_student,
                                                       course_blocks)
        # Update database
        if (CourseTime.objects.filter(course_id=course_key, student_id=student.id).count() == 0):
            # Create entry
            CourseTime.objects.create(student_id=student.id,
                                      course_id=course_key,
                                      time_spent=time_chapters_student)
        else:
            # Update entry
            CourseTime.objects.filter(course_id=course_key, student_id=student.id).update(time_spent=time_chapters_student,
                                                                                          last_calc=datetime.datetime.now())
        # Add student time to his groups
        time_chapters_all = add_time_chapter_time(time_chapters_all, time_chapters_student)
        
        if StudentGrades.objects.filter(course_id=course_key, student_id=student.id).count() > 0:
            grade_group = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)[0].grade_group
            if grade_group == 'PROF':
                 time_chapters_prof = add_time_chapter_time(time_chapters_prof, time_chapters_student)
            elif grade_group == 'OK':
                 time_chapters_ok = add_time_chapter_time(time_chapters_ok, time_chapters_student)
            elif grade_group == 'FAIL':
                 time_chapters_fail = add_time_chapter_time(time_chapters_fail, time_chapters_student)
    # Add group all time chapters to database
    if (CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.ALL_STUDENTS).count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.ALL_STUDENTS,
                                  course_id=course_key,
                                  time_spent=time_chapters_all)
    else:
        # Update entry
        CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.ALL_STUDENTS).update(time_spent=time_chapters_all,
                                                                                                   last_calc=datetime.datetime.now())
    # Add group prof time chapters to database
    if (CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.PROF_GROUP).count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.PROF_GROUP,
                                  course_id=course_key,
                                  time_spent=time_chapters_prof)
    else:
        # Update entry
        CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.PROF_GROUP).update(time_spent=time_chapters_prof,
                                                                                                 last_calc=datetime.datetime.now())
    # Add group ok time chapters to database
    if (CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.PASS_GROUP).count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.PASS_GROUP,
                                  course_id=course_key,
                                  time_spent=time_chapters_ok)
    else:
        # Update entry
        CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.PASS_GROUP).update(time_spent=time_chapters_ok,
                                                                                                 last_calc=datetime.datetime.now())
    # Add group fail time chapters to database
    if (CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.FAIL_GROUP).count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.FAIL_GROUP,
                                  course_id=course_key,
                                  time_spent=time_chapters_fail)
    else:
        # Update entry
        CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.FAIL_GROUP).update(time_spent=time_chapters_fail,
                                                                                                 last_calc=datetime.datetime.now())
    

def get_DB_course_spent_time(course_key, student_id=None):
    """
    Return course spent time from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    # Course struct
    course_struct = get_DB_course_struct(course_key, include_unreleased=False)
    
    # Students time
    students_time = {}
    if student_id is None:
        sql_time = CourseTime.objects.filter(course_id=course_key)
    else:
        sql_time = CourseTime.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_time in sql_time:
        students_time[std_time.student_id] = ast.literal_eval(std_time.time_spent)
        
    return course_struct, students_time           
              
              
######################################################################
####################### SECTION ACCESSES #############################
######################################################################

def create_access_chapters(course_key):
    """
    Creates an array of chapters with times for each one
    """
    
    access_chapters = {}
    
    chapters = CourseStruct.objects.filter(course_id=course_key, section_type='chapter')
    
    for chapter in chapters:
        chapter_elem = {'accesses': 0,
                        'sequentials': {}}
        sequentials = CourseStruct.objects.filter(course_id=course_key, section_type='sequential', father=chapter)
        for seq in sequentials:
            chapter_elem['sequentials'][seq.id] = {'accesses': 0,
                                                   'verticals': {},
                                                   'last_vert': 1}
            verticals = CourseStruct.objects.filter(course_id=course_key, section_type='vertical', father=seq)
            for vert in verticals:
                chapter_elem['sequentials'][seq.id]['verticals'][vert.id] = {'accesses': 0}
        access_chapters[chapter.id] = chapter_elem
   
    return access_chapters

def get_student_section_accesses(course_key, student, access_chapters=None):
    """
    Fill course structure with accesses to each section for given course and student
    """
    if access_chapters is None:
        access_chapters = create_access_chapters(course_key)
        
    events = get_course_access_events_sql(course_key, student) 
    
    cur_vert = 0
    cur_chapt = None
    cur_seq = None
    for event in events:
        if event.event_source == 'server':
            course, chapt_key, seq_key = get_locations_from_url(event.event_type)
            # Get chapter and seq id
            if chapt_key is not None and CourseStruct.objects.filter(module_state_key=chapt_key).count() > 0:
                cur_chapt = CourseStruct.objects.filter(module_state_key=chapt_key)[0].id
                if seq_key is not None and CourseStruct.objects.filter(module_state_key=seq_key, father_id=cur_chapt).count() > 0:
                    cur_seq = CourseStruct.objects.filter(module_state_key=seq_key, father_id=cur_chapt)[0].id
                else:
                    cur_seq = None
            else:
                cur_chapt = None
                cur_seq = None
                
            if course is not None and cur_chapt is not None:
                if cur_seq is not None:
                    cur_vert = access_chapters[cur_chapt]['sequentials'][cur_seq]['last_vert']
                    # Add sequential access
                    access_chapters = add_course_access(access_chapters, cur_chapt, cur_seq, None)
                    # Add 1st vertical access
                    access_chapters = add_course_access(access_chapters, cur_chapt, cur_seq, cur_vert)
                else:
                    # Add chapter access
                    access_chapters = add_course_access(access_chapters, cur_chapt, None, None)
                    cur_vert = 0
        else:
            if cur_chapt is not None and cur_seq is not None:
                event_data = ast.literal_eval(event.event)
                if ((event.event_type == 'seq_prev' or 
                     event.event_type == 'seq_next' or 
                     event.event_type == 'seq_goto') and
                    event_data['old'] != event_data['new']):
                    cur_vert = event_data['new']
                    access_chapters[cur_chapt]['sequentials'][cur_seq]['last_vert'] = cur_vert
                    # Add vertical access
                    access_chapters = add_course_access(access_chapters, cur_chapt, cur_seq, cur_vert)
            
    return access_chapters


def add_student_accesses(original, new):
    """
    Add time in chapter_time new to chapter_time original
    """
    if original.keys() != new.keys():
        ## TODO exception
        return
    
    for ch_id in original.keys():
        original[ch_id]['accesses'] += new[ch_id]['accesses']
        if original[ch_id]['sequentials'].keys() != new[ch_id]['sequentials'].keys():
            ## TODO exception
            return
        for seq_id in original[ch_id]['sequentials'].keys():
            original[ch_id]['sequentials'][seq_id]['accesses'] += new[ch_id]['sequentials'][seq_id]['accesses']
            if original[ch_id]['sequentials'][seq_id]['verticals'].keys() != new[ch_id]['sequentials'][seq_id]['verticals'].keys():
                ## TODO exception
                return
            for vert_id in original[ch_id]['sequentials'][seq_id]['verticals'].keys():
                original[ch_id]['sequentials'][seq_id]['verticals'][vert_id]['accesses'] += new[ch_id]['sequentials'][seq_id]['verticals'][vert_id]['accesses']

    return original


def add_course_access(access_chapters, chapt_id, seq_id=None, vert_pos=None):
    """
    Add access to course section
    """
    if seq_id is None:
        # Chapter access
        access_chapters[chapt_id]['accesses'] += 1
    else:
        if vert_pos is None:
            # Sequential access
            access_chapters[chapt_id]['sequentials'][seq_id]['accesses'] += 1
            # Chapter access
            access_chapters[chapt_id]['accesses'] += 1
        else:
            # Vertical access
            if CourseStruct.objects.filter(father_id=seq_id, index=vert_pos).count() > 0:
                vert_id = CourseStruct.objects.filter(father_id=seq_id, index=vert_pos)[0].id
                access_chapters[chapt_id]['sequentials'][seq_id]['verticals'][vert_id]['accesses'] += 1
                        
    return access_chapters


def update_DB_course_section_accesses(course_key):
    """
    Recalculate course section accesses and update data in database
    """
    
    course_accesses = create_access_chapters(course_key)
    # Student groups time chapters
    course_accesses_all = copy.deepcopy(course_accesses)
    course_accesses_prof = copy.deepcopy(course_accesses)
    course_accesses_ok = copy.deepcopy(course_accesses)
    course_accesses_fail = copy.deepcopy(course_accesses)
    
    students = get_course_students(course_key)
    
    # Add students time chapters to database
    for student in students:
        course_accesses_student = copy.deepcopy(course_accesses)
        course_accesses_student = get_student_section_accesses(course_key,
                                                               student,
                                                               course_accesses_student)
        # Update database
        if (CourseAccesses.objects.filter(course_id=course_key, student_id=student.id).count() == 0):
            # Create entry
            CourseAccesses.objects.create(student_id=student.id,
                                          course_id=course_key,
                                          accesses=course_accesses_student)
        else:
            # Update entry
            CourseAccesses.objects.filter(course_id=course_key, student_id=student.id).update(accesses=course_accesses_student,
                                                                                              last_calc=datetime.datetime.now())
        # Add student time to his groups
        course_accesses_all = add_student_accesses(course_accesses_all, course_accesses_student)
        
        if StudentGrades.objects.filter(course_id=course_key, student_id=student.id).count() > 0:
            grade_group = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)[0].grade_group
            if grade_group == 'PROF':
                 course_accesses_prof = add_student_accesses(course_accesses_prof, course_accesses_student)
            elif grade_group == 'OK':
                 course_accesses_ok = add_student_accesses(course_accesses_ok, course_accesses_student)
            elif grade_group == 'FAIL':
                 course_accesses_fail = add_student_accesses(course_accesses_fail, course_accesses_student)
    # Add group all time chapters to database
    if (CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.ALL_STUDENTS).count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.ALL_STUDENTS,
                                      course_id=course_key,
                                      accesses=course_accesses_all)
    else:
        # Update entry
        CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.ALL_STUDENTS).update(accesses=course_accesses_all,
                                                                                                           last_calc=datetime.datetime.now())
    # Add group prof time chapters to database
    if (CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.PROF_GROUP).count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.PROF_GROUP,
                                      course_id=course_key,
                                      accesses=course_accesses_prof)
    else:
        # Update entry
        CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.PROF_GROUP).update(accesses=course_accesses_prof,
                                                                                                         last_calc=datetime.datetime.now())
    # Add group ok time chapters to database
    if (CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.PASS_GROUP).count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.PASS_GROUP,
                                      course_id=course_key,
                                      accesses=course_accesses_ok)
    else:
        # Update entry
        CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.PASS_GROUP).update(accesses=course_accesses_ok,
                                                                                                         last_calc=datetime.datetime.now())
    # Add group fail time chapters to database
    if (CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.FAIL_GROUP).count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.FAIL_GROUP,
                                      course_id=course_key,
                                      accesses=course_accesses_fail)
    else:
        # Update entry
        CourseAccesses.objects.filter(course_id=course_key, student_id=CourseAccesses.FAIL_GROUP).update(accesses=course_accesses_fail,
                                                                                                         last_calc=datetime.datetime.now())


def get_DB_course_section_accesses(course_key, student_id=None):
    """
    Return course section accesses from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    # Course struct
    course_struct = get_DB_course_struct(course_key, include_verticals=True, include_unreleased=False)
    
    # Students time
    students_accesses = {}
    if student_id is None:
        sql_accesses = CourseAccesses.objects.filter(course_id=course_key)
    else:
        sql_accesses = CourseAccesses.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_accesses in sql_accesses:
        students_accesses[std_accesses.student_id] = ast.literal_eval(std_accesses.accesses)
    
    return course_struct, students_accesses



