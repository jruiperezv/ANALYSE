
from courseware.grades import iterate_grades_for
from courseware.models import StudentModule
from data import *
from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from models import (SortGrades, CourseTime, CourseStruct, 
                    StudentGrades, CourseAccesses, 
                    CourseProbVidProgress)
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
        chapters_sql_filtered = chapters_sql.filter(module_state_key=chapter['id'])
        if (chapters_sql_filtered.count() == 0):
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
            chapters_sql_filtered.update(name=chapter['name'],
                                         section_type='chapter',
                                         graded=chapter['graded'],
                                         released=chapter['released'],
                                         index=chapter_index)
        # Sequentials
        seq_index = 1
        chapt_seq_sql = sequentials_sql.filter(father=chapters_sql.get(module_state_key=chapter['id']))
        for sequential in chapter['sequentials']:
            chapt_seq_sql_filtered = chapt_seq_sql.filter(module_state_key=sequential['id'])
            if(chapt_seq_sql_filtered.count() == 0):
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
                chapt_seq_sql_filtered.update(name=sequential['name'],
                                              section_type='sequential',
                                              graded=sequential['graded'],
                                              released=sequential['released'],
                                              index=seq_index)
            seq_index += 1
            
            # Verticals
            vert_index = 1
            seq_vert_sql = verticals_sql.filter(father=sequentials_sql.get(module_state_key=sequential['id']))
            for vertical in sequential['verticals']:
                seq_ver_sql_filtered = seq_vert_sql.filter(module_state_key=vertical['id'])
                if(seq_ver_sql_filtered.count() == 0):
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
                    seq_ver_sql_filtered.update(name=vertical['name'],
                                                section_type='vertical',
                                                graded=vertical['graded'],
                                                released=vertical['released'],
                                                index=vert_index)
                vert_index += 1
        chapter_index += 1
    
    
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
        ws_sql_filtered = ws_sql.filter(label=subsection['category'])
        if (ws_sql.count() == 0 or 
            ws_sql_filtered.count() == 0):
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
            ws_sql_filtered.update(sort_type='WS',
                                   label=subsection['category'],
                                   category=subsection['category'],
                                   name=subsection['category'],
                                   num_not=subsection['NOT'],
                                   num_fail=subsection['FAIL'],
                                   num_pass=subsection['OK'],
                                   num_prof=subsection['PROFICIENCY'])

    
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
        gs_sql_filtered = gs_sql.filter(label=section['label'])
        if (gs_sql.count() == 0 or 
            gs_sql_filtered.count() == 0):
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
            gs_sql_filtered.update(sort_type='GS',
                                   label=section['label'],
                                   category=section['category'],
                                   name=section['name'],
                                   num_not=section['NOT'],
                                   num_fail=section['FAIL'],
                                   num_pass=section['OK'],
                                   num_prof=section['PROFICIENCY'])
    

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
    total_score = 0.0
    total_weight = 0.0
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
                                                            'total': 0.0,
                                                            'score': None,
                                                            'done': True})
                weight_data[subsection['category']] = {'index': index, 'score': None, 'total': 0.0,
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
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    prof_std_grades = copy.deepcopy(sort_homework_std)
    prof_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    pass_std_grades = copy.deepcopy(sort_homework_std)
    pass_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    fail_std_grades = copy.deepcopy(sort_homework_std)
    fail_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    all_count = 0
    prof_count = 0
    pass_count = 0
    fail_count = 0
    
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit
    
    total_aux = 0.0
    
    for student in students:
        std_grades = get_student_grades(course_key, student, full_gc,
                                        copy.deepcopy(sort_homework_std),
                                        copy.deepcopy(weight_data_std))
        
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
            exists.update(grades=std_grades, grade_group=grade_type, last_calc=timezone.now())
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
        exists.update(grades=all_std_grades, grade_group=all_grade_type, last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.ALL_STUDENTS,
                                     grades=all_std_grades,
                                     grade_group=all_grade_type)
    # Proficiency
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.PROF_GROUP)
    if exists.count() > 0:
        exists.update(grades=prof_std_grades, grade_group='PROF', last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.PROF_GROUP,
                                     grades=prof_std_grades,
                                     grade_group='PROF')
    # Pass
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.PASS_GROUP)
    if exists.count() > 0:
        exists.update(grades=pass_std_grades, grade_group='OK', last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.PASS_GROUP,
                                     grades=pass_std_grades,
                                     grade_group='OK')
    # Fail
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.FAIL_GROUP)
    if exists.count() > 0:
        exists.update(grades=fail_std_grades, grade_group='FAIL', last_calc=timezone.now())
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
                                              timezone.now())
    
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
        filtered_coursetime = CourseTime.objects.filter(course_id=course_key, student_id=student.id)
        if (filtered_coursetime.count() == 0):
            # Create entry
            CourseTime.objects.create(student_id=student.id, course_id=course_key,
                                      time_spent=time_chapters_student)
        else:
            # Update entry
            filtered_coursetime.update(time_spent=time_chapters_student, last_calc=timezone.now())
            
        # Add student time to his groups
        time_chapters_all = add_time_chapter_time(time_chapters_all, time_chapters_student)
        
        filtered_studentgrades = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
        if filtered_studentgrades.count() > 0:
            grade_group = filtered_studentgrades[0].grade_group
            if grade_group == 'PROF':
                time_chapters_prof = add_time_chapter_time(time_chapters_prof, time_chapters_student)
            elif grade_group == 'OK':
                time_chapters_ok = add_time_chapter_time(time_chapters_ok, time_chapters_student)
            elif grade_group == 'FAIL':
                time_chapters_fail = add_time_chapter_time(time_chapters_fail, time_chapters_student)
    
    # Add group all time chapters to database
    coursetime_filter_all = CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.ALL_STUDENTS)
    if (coursetime_filter_all.count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.ALL_STUDENTS, course_id=course_key, 
                                  time_spent=time_chapters_all)
    else:
        # Update entry
        coursetime_filter_all.update(time_spent=time_chapters_all, last_calc=timezone.now())
    
    # Add group prof time chapters to database
    coursetime_filter_prof = CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.PROF_GROUP)
    if (coursetime_filter_prof.count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.PROF_GROUP,course_id=course_key, 
                                  time_spent=time_chapters_prof)
    else:
        # Update entry
        coursetime_filter_prof.update(time_spent=time_chapters_prof, last_calc=timezone.now())
    
    # Add group ok time chapters to database
    coursetime_filter_pass = CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.PASS_GROUP)
    if (coursetime_filter_pass.count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.PASS_GROUP, course_id=course_key, 
                                  time_spent=time_chapters_ok)
    else:
        # Update entry
        coursetime_filter_pass.update(time_spent=time_chapters_ok, last_calc=timezone.now())
    
    # Add group fail time chapters to database
    coursetime_filter_fail = CourseTime.objects.filter(course_id=course_key, student_id=CourseTime.FAIL_GROUP)
    if (coursetime_filter_fail.count() == 0):
        # Create entry
        CourseTime.objects.create(student_id=CourseTime.FAIL_GROUP, course_id=course_key, 
                                  time_spent=time_chapters_fail)
    else:
        # Update entry
        coursetime_filter_fail.update(time_spent=time_chapters_fail, last_calc=timezone.now())


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
        courseaccesses_filtered = CourseAccesses.objects.filter(course_id=course_key, student_id=student.id)
        if (courseaccesses_filtered.count() == 0):
            # Create entry
            CourseAccesses.objects.create(student_id=student.id, course_id=course_key,
                                          accesses=course_accesses_student)
        else:
            # Update entry
            courseaccesses_filtered.update(accesses=course_accesses_student, last_calc=timezone.now())
        
        # Add student time to his groups
        course_accesses_all = add_student_accesses(course_accesses_all, course_accesses_student)
        studentgrades_filtered = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
        if studentgrades_filtered.count() > 0:
            grade_group = studentgrades_filtered[0].grade_group
            if grade_group == 'PROF':
                course_accesses_prof = add_student_accesses(course_accesses_prof, course_accesses_student)
            elif grade_group == 'OK':
                course_accesses_ok = add_student_accesses(course_accesses_ok, course_accesses_student)
            elif grade_group == 'FAIL':
                course_accesses_fail = add_student_accesses(course_accesses_fail, course_accesses_student)
    
    # Add group all time chapters to database
    courseaccess_filter_all = CourseAccesses.objects.filter(course_id=course_key, 
                                                            student_id=CourseAccesses.ALL_STUDENTS)
    if (courseaccess_filter_all.count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.ALL_STUDENTS, course_id=course_key,
                                      accesses=course_accesses_all)
    else:
        # Update entry
        courseaccess_filter_all.update(accesses=course_accesses_all, last_calc=timezone.now())
    
    # Add group prof time chapters to database
    courseaccess_filter_prof = CourseAccesses.objects.filter(course_id=course_key, 
                                                             student_id=CourseAccesses.PROF_GROUP)
    if (courseaccess_filter_prof.count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.PROF_GROUP, course_id=course_key,
                                      accesses=course_accesses_prof)
    else:
        # Update entry
        courseaccess_filter_prof.update(accesses=course_accesses_prof, last_calc=timezone.now())
    
    # Add group ok time chapters to database
    courseaccess_filter_pass = CourseAccesses.objects.filter(course_id=course_key, 
                                                             student_id=CourseAccesses.PASS_GROUP)
    if (courseaccess_filter_pass.count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.PASS_GROUP, course_id=course_key,
                                      accesses=course_accesses_ok)
    else:
        # Update entry
        courseaccess_filter_pass.update(accesses=course_accesses_ok, last_calc=timezone.now())
    
    # Add group fail time chapters to database
    courseaccess_filter_fail = CourseAccesses.objects.filter(course_id=course_key, 
                                                             student_id=CourseAccesses.FAIL_GROUP)
    if (courseaccess_filter_fail.count() == 0):
        # Create entry
        CourseAccesses.objects.create(student_id=CourseAccesses.FAIL_GROUP, course_id=course_key,
                                      accesses=course_accesses_fail)
    else:
        # Update entry
        courseaccess_filter_fail.update(accesses=course_accesses_fail, last_calc=timezone.now())


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
    
    
##############################################################################
######################### PROBLEMS + VIDEO PROGRESS ##########################
##############################################################################

def create_course_progress(course_key):
    """
    Returns course structure and timeline to calculate video and problem
    progress
    """
    course = get_course_module(course_key)
    
    # Get timeline
    timeline = perdelta(course.start, course.end if course.end is not None else timezone.now(), timedelta(days=1))
    
    # Get course struct
    course_struct = []
    
    full_gc = dump_full_grading_context(course)
    
    index = 0
    for subsection in full_gc['weight_subsections']:
        course_struct.append({'weight': subsection['weight'],
                              'total': 0.0,
                              'score': 0.0,
                              'problems': [] })
        for grad_section in full_gc['graded_sections']:
            if grad_section['released'] and grad_section['category'] == subsection['category']:
                course_struct[index]['total'] += grad_section['max_grade']
                # Add problems ids
                for prob in grad_section['problems']:
                    course_struct[index]['problems'].append(prob.location)
        index += 1
        
    # Delete non released or graded sections
    for section in course_struct:
        if section['total'] == 0:
            course_struct.remove(section)
    
    return course_struct, timeline
    
    
def perdelta(start, end, delta):
    """
    Returns a datatime array starting at start and ending at
    end, with a separation of delta
    """
    timeline = []
    curr = start
    while curr <= end:
        timeline.append(curr)
        curr += delta
    return timeline


def get_student_problem_progress(course_key, student, course_struct=None, timeline=None):
    """
    Return problem progress for a given course and student
    """
    if course_struct is None or timeline is None:
        course_struct, timeline = create_course_progress(course_key)
    
    problem_progress = []
    
    events = get_problem_history_sql(course_key, student)
    last_time = timezone.make_aware(datetime.datetime.fromtimestamp(0),timezone.UTC())
    for act_time in timeline:
        filter_events = events.filter(dtcreated__gt = last_time,
                                      dtcreated__lte = act_time)
        last_time = act_time
        # Add grades
        for event in filter_events:
            prob_data = ast.literal_eval(event.event)
            prob_block = course_key.make_usage_key_from_deprecated_string(prob_data['problem_id'])
            for section in course_struct:
                for prob in section['problems']:
                    if prob == prob_block:
                        if event.event_type == 'problem_check':
                            section['score'] += prob_data['grade']
                        elif event.event_type == 'problem_rescore':
                            section['score'] -= prob_data['orig_score']
                            section['score'] += prob_data['new_score']
                        break
        # Add data
        total = 0.0
        total_weight = 0.0
        for section in course_struct:
            if section['total'] != 0:
                total += (section['score']/section['total'])*section['weight']
            total_weight += section['weight']

        total = total/total_weight
        total = total*100
        total = int(round(total,0))
        
        problem_progress.append({'score':total, 'time': act_time})
    
    return problem_progress


def mean_problem_progress_sum(problem_progress, num):
    if num <= 1:
        return problem_progress
    
    for p in problem_progress:
        p['score'] = p['score']/num
        
    return problem_progress 

def add_problem_progress(base, new):
    
    for i in range(len(base)):
        base[i]['score'] += new[i]['score']
    return base


def optimize_problem_progress(problem_progress):
    
    time_len = len(problem_progress)
    if time_len == 1:
        return ([problem_progress[0]['score']], problem_progress[0]['time'],
                problem_progress[0]['time'], 0)
    if time_len == 0:
        return ([0], None, None, 0)
    
    # Get start date
    start_index = 0
    
    while (start_index < time_len
           and problem_progress[start_index]['score'] == 0):
        start_index += 1
    
    if start_index == time_len:
        return ([0], None, None, 0)
    
    # Get end date
    last_score = problem_progress[time_len - 1]['score']
    end_index = start_index
    index_found = False
    
    for i in range(start_index,time_len):
        if problem_progress[i]['score'] == last_score:
            if not index_found: 
                end_index = i
                index_found = True
        else:
            end_index = i
            index_found = False
    
    # Get dates
    start_index = start_index - 1 if (start_index >= 1) else start_index
    end_index = end_index + 1 if (end_index < time_len -1) else end_index
    
    end_date = problem_progress[end_index]['time']
    start_date = problem_progress[start_index]['time']
    
    tdelta =  0 if (start_index == end_index) else (problem_progress[1]['time'] - problem_progress[0]['time'])
    delta = (tdelta.days*60*60*24 + tdelta.seconds) if tdelta is not 0 else 0
    
    # Get progress array
    progress = []
    for i in range(start_index, end_index + 1):
        progress.append(problem_progress[i]['score'])
        
    return progress, start_date, end_date, delta


def update_DB_course_problem_progress(course_key, course_struct=None, timeline=None):
    """
    Update problem progress in database
    """
    if course_struct is None or timeline is None:
        course_struct, timeline = create_course_progress(course_key)
        
    all_problem_progress = []
    prof_problem_progress = []
    ok_problem_progress = []
    fail_problem_progress = []
    num_all = 0
    num_prof = 0
    num_ok = 0
    num_fail = 0
    
    for time in timeline:
        all_problem_progress.append({'score':0, 'time':time})
        prof_problem_progress.append({'score':0, 'time':time})
        ok_problem_progress.append({'score':0, 'time':time})
        fail_problem_progress.append({'score':0, 'time':time})
        
    students = get_course_students(course_key)
    
    for student in students:
        std_problem_progress = get_student_problem_progress(course_key,
                                                            student,
                                                            copy.deepcopy(course_struct),
                                                            timeline)
        # Add grade to all
        all_problem_progress = add_problem_progress(all_problem_progress, 
                                                    std_problem_progress)
        num_all += 1
        # Add grade to category
        studentgrades_filtered = StudentGrades.objects.filter(course_id=course_key, 
                                                              student_id=student.id)
        if studentgrades_filtered.count() > 0:
            grade_group = studentgrades_filtered[0].grade_group
            if grade_group == 'PROF':
                prof_problem_progress = add_problem_progress(prof_problem_progress,
                                                             std_problem_progress)
                num_prof += 1
            elif grade_group == 'OK':
                ok_problem_progress = add_problem_progress(ok_problem_progress,
                                                             std_problem_progress)
                num_ok += 1
            elif grade_group == 'FAIL':
                fail_problem_progress = add_problem_progress(fail_problem_progress,
                                                             std_problem_progress)
                num_fail += 1
        
        progress, start_date, end_date, delta = optimize_problem_progress(std_problem_progress)
        # Add student progress to database
        sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, 
                                                            student_id=student.id, type='PROB')
        if (sql_filtered.count() == 0):
            # Create entry
            CourseProbVidProgress.objects.create(student_id=student.id,
                                                 course_id=course_key,
                                                 progress=progress,
                                                 type='PROB',
                                                 start_time=start_date,
                                                 end_time=end_date,
                                                 delta=delta)
        else:
            # Update entry
            sql_filtered.update(progress=progress,
                                start_time=start_date,
                                end_time=end_date,
                                delta=delta,
                                last_calc=timezone.now())
    
    # Add ALL students progress to database
    all_problem_progress = mean_problem_progress_sum(all_problem_progress, num_all)
    progress, start_date, end_date, delta = optimize_problem_progress(all_problem_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.ALL_STUDENTS)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.ALL_STUDENTS,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())
        
    # Add FAIL students progress to database
    fail_problem_progress = mean_problem_progress_sum(fail_problem_progress, num_fail)
    progress, start_date, end_date, delta = optimize_problem_progress(fail_problem_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.FAIL_GROUP)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.FAIL_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())
    
    # Add PROFICIENCY students progress to database
    prof_problem_progress = mean_problem_progress_sum(prof_problem_progress, num_prof)
    progress, start_date, end_date, delta = optimize_problem_progress(prof_problem_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.PROF_GROUP)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PROF_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())
    
    # Add PASS students progress to database
    ok_problem_progress = mean_problem_progress_sum(ok_problem_progress, num_ok)
    progress, start_date, end_date, delta = optimize_problem_progress(ok_problem_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.PASS_GROUP)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PASS_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())


def get_student_video_progress(course, student, timeline=None):
    """
    Get video progress for a given course and student
    """
    if timeline is None:
        timeline = create_course_progress(course.location.course_key)[1]
    
    video_progress = []
    
    (video_module_ids, video_durations) = get_info_videos(course)[1:3]
    
    first_event, last_event = get_video_events_interval(student, course.location.course_key)
    
    last_percent = 0
    for act_time in timeline:
        if (first_event is None or
            (act_time < first_event and
            (first_event - act_time).days > 0)):
            video_progress.append({'percent': 0, 
                                   'time': act_time})
        elif (act_time > last_event and
              (act_time - last_event).days > 0):
            video_progress.append({'percent': last_percent, 
                                   'time': act_time})
        else:
            last_percent = student_total_video_percent(course, student, video_module_ids, video_durations, act_time)
            video_progress.append({'percent': last_percent, 
                                   'time': act_time})
    
    return video_progress


def student_total_video_percent(course, user, video_module_ids = None, video_durations = None, last_date = None):
    """
        based in HECTOR's video_consumption 
        Returns video consumption in the form of video names, percentages
        per video seen and total time spent per video for a certain user
    """
    if video_module_ids is None or video_durations is None:
        (video_module_ids, video_durations) = get_info_videos(course)[1:2]
    
    # Non-overlapped video time
    stu_video_seen = []
    # Video length seen based on tracking-log events (best possible measure)
    for video_module_id in video_module_ids:
        [aux_start, aux_end] = video_len_watched(user,video_module_id, last_date)
        interval_sum = 0
        for start, end in zip(aux_start,aux_end):
            interval_sum += end - start
        stu_video_seen.append(interval_sum)
        
    if sum(stu_video_seen) <= 0:
        return 0
        
    video_percentages = map(truediv, stu_video_seen, video_durations)
    video_percentages = [val*100 for val in video_percentages]
    video_percentages = [int(round(val,0)) for val in video_percentages]
    # Ensure artificially percentages do not surpass 100%, which
    # could happen slightly from the 1s adjustment in id_to_length function
    for i in range(0,len(video_percentages)):
        if video_percentages[i] > 100:
            video_percentages[i] = 100
            
    total_percent = sum(video_percentages)/len(video_percentages)
  
    return total_percent


def mean_video_progress_sum(video_progress, num):
    if num <= 1:
        return video_progress
    
    for p in video_progress:
        p['percent'] = p['percent']/num
        
    return video_progress 

def add_video_progress(base, new):
    
    for i in range(len(base)):
        base[i]['percent'] += new[i]['percent']
    return base


def optimize_video_progress(video_progress):
    
    time_len = len(video_progress)
    if time_len == 1:
        return ([video_progress[0]['percent']], video_progress[0]['time'],
                video_progress[0]['time'], 0)
    if time_len == 0:
        return ([0], None, None, 0)
    
    # Get start date
    start_index = 0
    
    while (start_index < time_len
           and video_progress[start_index]['percent'] == 0):
        start_index += 1
    
    if start_index == time_len:
        return ([0], None, None, 0)
    
    # Get end date
    last_percent = video_progress[time_len - 1]['percent']
    end_index = start_index
    index_found = False
    
    for i in range(start_index,time_len):
        if video_progress[i]['percent'] == last_percent:
            if not index_found: 
                end_index = i
                index_found = True
        else:
            end_index = i
            index_found = False
    
    # Get dates
    start_index = start_index - 1 if (start_index >= 1) else start_index
    end_index = end_index + 1 if (end_index < time_len -1) else end_index
    
    end_date = video_progress[end_index]['time']
    start_date = video_progress[start_index]['time']
    
    tdelta =  0 if (start_index == end_index) else (video_progress[1]['time'] - video_progress[0]['time'])
    delta = (tdelta.days*60*60*24 + tdelta.seconds) if tdelta is not 0 else 0
    
    # Get progress array
    progress = []
    for i in range(start_index, end_index + 1):
        progress.append(video_progress[i]['percent'])
        
    return progress, start_date, end_date, delta


def update_DB_course_video_progress(course_key, timeline=None):
    
    if timeline is None:
        timeline = create_course_progress(course_key)[1]
        
    all_video_progress = []
    prof_video_progress = []
    ok_video_progress = []
    fail_video_progress = []
    num_all = 0
    num_prof = 0
    num_ok = 0
    num_fail = 0
    
    for time in timeline:
        all_video_progress.append({'percent':0, 'time':time})
        prof_video_progress.append({'percent':0, 'time':time})
        ok_video_progress.append({'percent':0, 'time':time})
        fail_video_progress.append({'percent':0, 'time':time})
        
    students = get_course_students(course_key)
    course = get_course_module(course_key)
    
    for student in students:
        std_video_progress = get_student_video_progress(course, student, timeline)
        # Add grade to all
        all_video_progress = add_video_progress(all_video_progress, 
                                                std_video_progress)
        num_all += 1
        # Add grade to category
        studentgrades_filtered =  StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
        if studentgrades_filtered.count() > 0:
            grade_group = studentgrades_filtered[0].grade_group
            if grade_group == 'PROF':
                prof_video_progress = add_video_progress(prof_video_progress,
                                                         std_video_progress)
                num_prof += 1
            elif grade_group == 'OK':
                ok_video_progress = add_video_progress(ok_video_progress,
                                                       std_video_progress)
                num_ok += 1
            elif grade_group == 'FAIL':
                fail_video_progress = add_video_progress(fail_video_progress,
                                                         std_video_progress)
                num_fail += 1
        
        progress, start_date, end_date, delta = optimize_video_progress(std_video_progress)
        # Add student progress to database
        sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, student_id=student.id, type='VID')
        if (sql_filtered.count() == 0):
            # Create entry
            CourseProbVidProgress.objects.create(student_id=student.id, course_id=course_key, progress=progress, 
                                                 type='VID', start_time=start_date,  end_time=end_date, delta=delta)
        else:
            # Update entry
            sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                                delta=delta, last_calc=timezone.now())
    
    # Add ALL students progress to database
    all_video_progress = mean_video_progress_sum(all_video_progress, num_all)
    progress, start_date, end_date, delta = optimize_video_progress(all_video_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.ALL_STUDENTS)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.ALL_STUDENTS,
                                             course_id=course_key,  progress=progress,
                                             type='VID', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())
        
    # Add FAIL students progress to database
    fail_video_progress = mean_video_progress_sum(fail_video_progress, num_fail)
    progress, start_date, end_date, delta = optimize_video_progress(fail_video_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.FAIL_GROUP)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.FAIL_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='VID', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())
    
    # Add PROFICIENCY students progress to database
    prof_video_progress = mean_video_progress_sum(prof_video_progress, num_prof)
    progress, start_date, end_date, delta = optimize_video_progress(prof_video_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.PROF_GROUP)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PROF_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='VID', start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date,
                            delta=delta, last_calc=timezone.now())
    
    # Add PASS students progress to database
    ok_video_progress = mean_video_progress_sum(ok_video_progress, num_ok)
    progress, start_date, end_date, delta = optimize_video_progress(ok_video_progress)
    # Add student progress to database
    sql_filtered = CourseProbVidProgress.objects.filter(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.PASS_GROUP)
    if (sql_filtered.count() == 0):
        # Create entry
        CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PASS_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='VID',  start_time=start_date,
                                             end_time=end_date, delta=delta)
    else:
        # Update entry
        sql_filtered.update(progress=progress, start_time=start_date, end_time=end_date, 
                            delta=delta, last_calc=timezone.now())


def get_DB_course_video_problem_progress(course_key, student_id=None):
    """
    Return course problem and video progress from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    # Students progress
    students_vidprob_progress = {}
    if student_id is None:
        sql_progress = CourseProbVidProgress.objects.filter(course_id=course_key)
    else:
        sql_progress = CourseProbVidProgress.objects.filter(course_id=course_key, student_id=student_id)
        
    for prob_progress in sql_progress.filter(type='PROB'):
        vid_progress = sql_progress.filter(type='VID', student_id=prob_progress.student_id)[0]
        # Start time
        if prob_progress.start_time is None:
            start_datetime = vid_progress.start_time
        elif vid_progress.start_time is None:
            start_datetime = prob_progress.start_time
        else:
            start_datetime = min(prob_progress.start_time, vid_progress.start_time)
        # End time
        if prob_progress.end_time is None:
            end_datetime = vid_progress.end_time
        elif vid_progress.end_time is None:
            end_datetime = prob_progress.end_time
        else:
            end_datetime = max(prob_progress.end_time, vid_progress.end_time)
        
        if prob_progress.delta == 0 or vid_progress.delta == 0:
            delta_l = prob_progress.delta if prob_progress.delta != 0 else vid_progress.delta 
        else:
            delta_l = min(prob_progress.delta, vid_progress.delta)
        delta = timedelta(seconds=delta_l)
        
        prob_data = ast.literal_eval(prob_progress.progress)
        vid_data = ast.literal_eval(vid_progress.progress)
        
        index_prob = 0
        index_vid = 0
        
        students_vidprob_progress[prob_progress.student_id] = []
        
        if (start_datetime is None or
            end_datetime is None or 
            delta == 0):
            return students_vidprob_progress
        
        for time in perdelta(start_datetime, end_datetime, delta):
            prob_result = 0
            if (prob_progress.start_time is not None and
                prob_progress.start_time <= time):
                if time <= prob_progress.end_time:
                    # time in problem timeline
                    prob_result = prob_data[index_prob]
                    index_prob += 1
                else:
                    # time > problem timeline
                    prob_result = prob_data[-1]
            else:
                # time < problem timeline
                prob_result = 0
                
            vid_result = 0
            if (vid_progress.start_time is not None and
                vid_progress.start_time <= time):
                if time <= vid_progress.end_time:
                    # time in video timeline
                    vid_result = vid_data[index_vid]
                    index_vid += 1
                else:
                    # time > video timeline
                    vid_result = vid_data[-1]
            else:
                # time < video timeline
                vid_result = 0
            
            # Add data
            students_vidprob_progress[prob_progress.student_id].append({'problems': prob_result,
                                                                        'videos': vid_result,
                                                                        'time': time.strftime("%d/%m/%Y")})
    
    return students_vidprob_progress


def to_iterable_module_id(block_usage_locator):
  
    iterable_module_id = []
    iterable_module_id.append(block_usage_locator.org)
    iterable_module_id.append(block_usage_locator.course)
    #iterable_module_id.append(block_usage_locator.run)
    iterable_module_id.append(block_usage_locator.branch)
    iterable_module_id.append(block_usage_locator.version_guid)
    iterable_module_id.append(block_usage_locator.block_type)
    iterable_module_id.append(block_usage_locator.block_id)    
    
    return iterable_module_id

