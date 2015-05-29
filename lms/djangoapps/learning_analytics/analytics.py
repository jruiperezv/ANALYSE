
from courseware.grades import iterate_grades_for
from courseware.models import StudentModule
from courseware.courses import get_course_by_id
from student.models import CourseEnrollment
from data import *
from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from models import *
from classes import *

from django.db.models import Q

import copy, datetime, ast, math, re

import simplejson as json

from operator import truediv
from django.utils import simplejson
import logging

import gdata.youtube
import gdata.youtube.service
from track.backends.django import TrackingLog

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
        [aux_start, aux_end] = video_len_watched_lastdate(user,video_module_id, last_date)
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

##########################################################################
######################## TIME SCHEDULE ###################################
##########################################################################
def time_schedule(course_id):
    students = get_course_students(course_id)
    
    morningTimeStudentCourse = 0
    afternoonTimeStudentCourse = 0
    nightTimeStudentCourse = 0
    
    for student in students:
        
        firstEventOfSeries = None
        previousEvent = None     
        
        morningTimeStudent = 0
        afternoonTimeStudent = 0
        nightTimeStudent = 0
        
        currentSchedule = ""
        
        studentEvents = get_all_events_sql(course_id, student)        
        
        for currentEvent in studentEvents:
            
            if(currentSchedule == ""):
                currentSchedule = current_schedule(currentEvent.dtcreated.hour)
                if(previousEvent == None):                    
                    firstEventOfSeries = currentEvent
                else:
                    firstEventOfSeries = previousEvent
            else:
                if((minutes_between(previousEvent.dtcreated,currentEvent.dtcreated) >= 30) or currentSchedule != current_schedule(currentEvent.dtcreated.hour)):                    
                    if(currentSchedule == "morning"):
                        morningTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                    elif(currentSchedule == "afternoon"):
                        afternoonTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                    elif(currentSchedule == "night"):
                        nightTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                        
                    currentSchedule = ""
                            
            previousEvent = currentEvent
            
        if(currentSchedule == "morning"):
            morningTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
        elif(currentSchedule == "afternoon"):
            afternoonTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
        elif(currentSchedule == "night"):
            nightTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
        
        morningTimeStudentCourse += morningTimeStudent
        afternoonTimeStudentCourse += afternoonTimeStudent
        nightTimeStudentCourse += nightTimeStudent
        
        timeSchedule = {'morningTime' : morningTimeStudent,
                        'afternoonTime' : afternoonTimeStudent,
                        'nightTime' : nightTimeStudent}
        
        # Update database
        if (TimeSchedule.objects.filter(course_id=course_id, student_id=student.id).count() == 0):
            
            TimeSchedule.objects.create(student_id=student.id, course_id=course_id, time_schedule=timeSchedule)
        else:
            # Update entry
            TimeSchedule.objects.filter(course_id=course_id, student_id=student.id).update(time_schedule=timeSchedule,last_calc=datetime.datetime.now())
    
    timeScheduleCourse = {'morningTime' : morningTimeStudentCourse,
                          'afternoonTime' : afternoonTimeStudentCourse,
                          'nightTime' : nightTimeStudentCourse}
        
    if(TimeSchedule.objects.filter(course_id=course_id, student_id=TimeSchedule.ALL_STUDENTS).count() == 0):
        TimeSchedule.objects.create(student_id=TimeSchedule.ALL_STUDENTS, course_id=course_id, time_schedule=timeScheduleCourse)
    else:
        # Update entry
        TimeSchedule.objects.filter(course_id=course_id, student_id=TimeSchedule.ALL_STUDENTS).update(time_schedule=timeScheduleCourse,
                                                                                      last_calc=datetime.datetime.now())
    
def current_schedule(hour):
    """
    Returns if the hour is in the morning, afternoon or night schedule
    hour: the hour of the time
    """ 
    currentSchedule = ""
    
    if( 6 < hour and hour < 14 ):
        currentSchedule = "morning"
    elif( 14 <= hour and hour < 21):
        currentSchedule = "afternoon"
    elif( hour <= 6 or hour == 21 or hour == 22 or hour == 23 or hour == 0):
        currentSchedule = "night"
    
    return currentSchedule

def get_DB_time_schedule(course_key, student_id=None):
    """
    Return course section accesses from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    student_time_schedule = {}
    if student_id is None:
        sql_time_schedule = TimeSchedule.objects.filter(course_id=course_key)
    else:
        sql_time_schedule = TimeSchedule.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_time_schedule in sql_time_schedule:
        student_time_schedule[std_time_schedule.student_id] = ast.literal_eval(std_time_schedule.time_schedule)
    
    return student_time_schedule

##########################################################################
######## Problem and Video Time Distribution # Video Time Watched ########
######## Repetition of Video Intervals # Video Event Distribution ########
#################### Daily Time on Problems and Videos ###################
##########################################################################

def update_visualization_data(course_key=None):
    # course_key should be a course_key
  
    kw_consumption_module = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'module_key': '',
        'display_name': '',
        'percent_viewed': 0,
        'total_time': 0,
    }
    
    kw_video_intervals = {
        'student': '',
        'course_key': course_key,
        'module_key': '',        
        'display_name': '',
        'hist_xaxis': '',
        'hist_yaxis': '',        
    }
    
    kw_daily_consumption = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'dates': '',
        'time_per_date': '',        
    }
    
    kw_video_events = {
        'student': '',
        'course_key': course_key,
        'module_key': '',          
        'display_name': '',
        'play_events' : '',
        'pause_events' : '',
        'change_speed_events' : '',
        'seek_from_events' : '',
        'seek_to_events' : '',
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.users_enrolled_in(course_key)]
        videos_in, problems_in = videos_problems_in(course)
        video_names, video_module_keys, video_durations = get_info_videos_descriptors(videos_in)
        problem_names = [x.display_name_with_default.encode('utf-8') for x in problems_in]
        problem_ids = [x.location for x in problems_in]
        
        # List of UserVideoIntervals
        users_video_intervals = []
        # List of UserTimeOnProblems
        users_time_on_problems = []
        for username_in in usernames_in:
            for video_module_key in video_module_keys:
                interval_start, interval_end, vid_start_time, vid_end_time = find_video_intervals(username_in, video_module_key)
                disjointed_start, disjointed_end = video_len_watched(interval_start, interval_end)
                users_video_intervals.append(UserVideoIntervals(username_in, video_module_key, 
                                                               interval_start, interval_end,
                                                               vid_start_time, vid_end_time,
                                                               disjointed_start, disjointed_end))
            for problem_id in problem_ids:
                problem_time, days, daily_time = time_on_problem(username_in, problem_id)
                users_time_on_problems.append(UserTimeOnProblems(username_in, problem_id, 
                                                                 problem_time, days, daily_time))          

        # ConsumptionModule table data
        accum_video_percentages = []
        accum_all_video_time = []
        accum_problem_time = []
        for username_in in usernames_in:
            kw_consumption_module['student'] = username_in
            #video modules
            kw_consumption_module['module_type'] = 'video'          
            # video_percentages (in %), all_video_time (in seconds)
            low_index = usernames_in.index(username_in)*len(video_names)
            high_index = low_index + len(video_names)
            video_percentages, all_video_time = video_consumption(users_video_intervals[low_index:high_index], video_durations)
            if video_percentages != [] and accum_video_percentages == []:
                accum_video_percentages = video_percentages
                accum_all_video_time = all_video_time
            elif video_percentages != []:
                for j in range(0, len(accum_all_video_time)):
                    accum_video_percentages[j] += video_percentages[j]
                    accum_all_video_time[j] += all_video_time[j]
            for i in range(0,len(video_percentages)):
                kw_consumption_module['module_key'] = video_module_keys[i]
                kw_consumption_module['display_name'] = video_names[i]
                kw_consumption_module['percent_viewed'] = video_percentages[i]
                kw_consumption_module['total_time'] = all_video_time[i]
                try:
                    new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                    new_entry.percent_viewed = kw_consumption_module['percent_viewed']
                    new_entry.total_time = kw_consumption_module['total_time']
                except ConsumptionModule.DoesNotExist:
                    new_entry = ConsumptionModule(**kw_consumption_module)
                new_entry.save()
            #problem modules
            kw_consumption_module['module_type'] = 'problem'
            kw_consumption_module['percent_viewed'] = None
            low_index = usernames_in.index(username_in)*len(problem_names)
            high_index = low_index + len(problem_names)   
            time_x_problem = problem_consumption(users_time_on_problems[low_index:high_index])
            if time_x_problem != [] and accum_problem_time == []:
                accum_problem_time = time_x_problem
            elif time_x_problem != []:
                for j in range(0, len(accum_problem_time)):
                    accum_problem_time[j] += time_x_problem[j]
                
            for i in range(0,len(time_x_problem)):
                kw_consumption_module['module_key'] = problem_ids[i]
                kw_consumption_module['display_name'] = problem_names[i]
                kw_consumption_module['total_time'] = time_x_problem[i]       
                try:
                    new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                    new_entry.total_time = kw_consumption_module['total_time']
                except ConsumptionModule.DoesNotExist:
                    new_entry = ConsumptionModule(**kw_consumption_module)                    
                new_entry.save()
        
        # average values
        kw_consumption_module['student'] = '#average'
        kw_consumption_module['module_type'] = 'video'                
        for i in range(0, len(accum_video_percentages)):
            accum_video_percentages[i] = int(round(truediv(accum_video_percentages[i],len(usernames_in)),0))
            #accum_all_video_time[i] = int(round(truediv(accum_all_video_time[i],len(usernames_in)),0))
            kw_consumption_module['module_key'] = video_module_keys[i]
            kw_consumption_module['display_name'] = video_names[i]
            kw_consumption_module['percent_viewed'] = accum_video_percentages[i]
            kw_consumption_module['total_time'] = accum_all_video_time[i]
            try:
                new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                new_entry.percent_viewed = kw_consumption_module['percent_viewed']
                new_entry.total_time = kw_consumption_module['total_time']
            except ConsumptionModule.DoesNotExist:
                new_entry = ConsumptionModule(**kw_consumption_module)            
            new_entry.save()
        kw_consumption_module['module_type'] = 'problem'
        kw_consumption_module['percent_viewed'] = None
        for i in range(0, len(accum_problem_time)):
            # Commented because we do not want the mean here but the total time
            #accum_problem_time[i] = truediv(accum_problem_time[i],len(usernames_in))
            kw_consumption_module['module_key'] = problem_ids[i]
            kw_consumption_module['display_name'] = problem_names[i]
            kw_consumption_module['total_time'] = accum_problem_time[i]
            try:
                new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                new_entry.total_time = kw_consumption_module['total_time']
            except ConsumptionModule.DoesNotExist:
                new_entry = ConsumptionModule(**kw_consumption_module)            
            new_entry.save()
 
        # VideoIntervals table data
        for video_name, video_id in zip(video_names, video_module_keys):
            accum_interval_start = []
            accum_interval_end = []
            accum_disjointed_start = []
            accum_disjointed_end = []          
            kw_video_intervals['module_key'] = video_id
            kw_video_intervals['display_name'] = video_name
            for username_in in usernames_in:
                kw_video_intervals['student'] = username_in      
                index = video_module_keys.index(video_id) + usernames_in.index(username_in)*len(video_names)
                interval_start = users_video_intervals[index].interval_start
                interval_end = users_video_intervals[index].interval_end
                accum_interval_start += interval_start
                accum_interval_end += interval_end
                accum_disjointed_start += users_video_intervals[index].disjointed_start
                accum_disjointed_end += users_video_intervals[index].disjointed_end                
                hist_xaxis, hist_yaxis = histogram_from_intervals(interval_start, interval_end, video_durations[video_module_keys.index(video_id)])
                kw_video_intervals['hist_xaxis'] = simplejson.dumps(hist_xaxis)
                kw_video_intervals['hist_yaxis'] = simplejson.dumps(hist_yaxis)
                try:
                    new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                    new_entry.hist_xaxis = kw_video_intervals['hist_xaxis']
                    new_entry.hist_yaxis = kw_video_intervals['hist_yaxis']
                except VideoIntervals.DoesNotExist:
                    new_entry = VideoIntervals(**kw_video_intervals)        
                new_entry.save()
            # Total times these video intervals have been viewed
            kw_video_intervals['student'] = '#class_total_times'
            interval_start, interval_end = sort_intervals(accum_interval_start, accum_interval_end)
            hist_xaxis, hist_yaxis = histogram_from_intervals(interval_start, interval_end, video_durations[video_module_keys.index(video_id)])
            kw_video_intervals['hist_xaxis'] = simplejson.dumps(hist_xaxis)
            kw_video_intervals['hist_yaxis'] = simplejson.dumps(hist_yaxis)
            try:
                new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                new_entry.hist_xaxis = kw_video_intervals['hist_xaxis']
                new_entry.hist_yaxis = kw_video_intervals['hist_yaxis']
            except VideoIntervals.DoesNotExist:
                new_entry = VideoIntervals(**kw_video_intervals)                    
            new_entry.save()
            
            # Total times these video intervals have been viewed
            # Every student counts a single time
            kw_video_intervals['student'] = '#one_stu_one_time'
            interval_start, interval_end = sort_intervals(accum_disjointed_start, accum_disjointed_end)
            hist_xaxis, hist_yaxis = histogram_from_intervals(interval_start, interval_end, video_durations[video_module_keys.index(video_id)])
            kw_video_intervals['hist_xaxis'] = simplejson.dumps(hist_xaxis)
            kw_video_intervals['hist_yaxis'] = simplejson.dumps(hist_yaxis)
            try:
                new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                new_entry.hist_xaxis = kw_video_intervals['hist_xaxis']
                new_entry.hist_yaxis = kw_video_intervals['hist_yaxis']
            except VideoIntervals.DoesNotExist:
                new_entry = VideoIntervals(**kw_video_intervals)                    
            new_entry.save()
            
        # DailyConsumption table data
        accum_vid_days = []
        accum_vid_daily_time = []
        accum_prob_days = []
        accum_prob_daily_time = []
        for username_in in usernames_in:
            low_index = usernames_in.index(username_in)*len(video_names)
            high_index = low_index + len(video_names)
            video_days, video_daily_time = daily_time_on_videos(users_video_intervals[low_index:high_index])
            video_days = datelist_to_isoformat(video_days)
            if len(video_days) > 0:
                accum_vid_days += video_days
                accum_vid_daily_time += video_daily_time
            low_index = usernames_in.index(username_in)*len(problem_names)
            high_index = low_index + len(problem_names)    
            problem_days, problem_daily_time = time_on_problems(users_time_on_problems[low_index:high_index])
            problem_days = datelist_to_isoformat(problem_days)
            if len(problem_days) > 0:
                accum_prob_days += problem_days
                accum_prob_daily_time += problem_daily_time
            # save to DailyConsumption table
            kw_daily_consumption['student'] = username_in
            kw_daily_consumption['module_type'] = 'video'
            kw_daily_consumption['dates'] = simplejson.dumps(video_days)
            kw_daily_consumption['time_per_date'] = simplejson.dumps(video_daily_time)
            try:
                new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
                new_entry.dates = kw_daily_consumption['dates']
                new_entry.time_per_date = kw_daily_consumption['time_per_date']
            except DailyConsumption.DoesNotExist:
                new_entry = DailyConsumption(**kw_daily_consumption)
            new_entry.save()            
            kw_daily_consumption['module_type'] = 'problem'
            kw_daily_consumption['dates'] = simplejson.dumps(problem_days)
            kw_daily_consumption['time_per_date'] = simplejson.dumps(problem_daily_time)
            try:
                new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
                new_entry.dates = kw_daily_consumption['dates']
                new_entry.time_per_date = kw_daily_consumption['time_per_date']
            except DailyConsumption.DoesNotExist:
                new_entry = DailyConsumption(**kw_daily_consumption)            
            new_entry.save()
            
        kw_daily_consumption['student'] = '#average'
        problem_days, problem_daily_time = class_time_on(accum_prob_days, accum_prob_daily_time)
        kw_daily_consumption['dates'] = simplejson.dumps(problem_days)
        kw_daily_consumption['time_per_date'] = simplejson.dumps(problem_daily_time)
        try:
            new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
            new_entry.dates = kw_daily_consumption['dates']
            new_entry.time_per_date = kw_daily_consumption['time_per_date']
        except DailyConsumption.DoesNotExist:
            new_entry = DailyConsumption(**kw_daily_consumption)        
        new_entry.save()
        kw_daily_consumption['module_type'] = 'video'
        video_days, video_daily_time = class_time_on(accum_vid_days, accum_vid_daily_time)
        kw_daily_consumption['dates'] = simplejson.dumps(video_days)
        kw_daily_consumption['time_per_date'] = simplejson.dumps(video_daily_time)
        try:
            new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
            new_entry.dates = kw_daily_consumption['dates']
            new_entry.time_per_date = kw_daily_consumption['time_per_date']
        except DailyConsumption.DoesNotExist:
            new_entry = DailyConsumption(**kw_daily_consumption)
        new_entry.save()            
            
        # VideoEvents table data
        VIDEO_EVENTS = ['play', 'pause', 'change_speed', 'seek_from', 'seek_to']
        class_events_times = [[],[],[],[],[]]
        for username_in in usernames_in:
            kw_video_events['student'] = username_in
            for video_module_key in video_module_keys:
                kw_video_events['module_key'] = video_module_key
                kw_video_events['display_name'] = video_names[video_module_keys.index(video_module_key)]
                events_times = get_video_events(username_in, video_module_key)
                if events_times is None:
                    continue
                for event in VIDEO_EVENTS:
                    kw_video_events[event + '_events'] = simplejson.dumps(events_times[VIDEO_EVENTS.index(event)])
                try:
                    new_entry = VideoEvents.objects.get(student=kw_video_events['student'], module_key=kw_video_events['module_key'])
                    new_entry.play_events = kw_video_events['play_events']
                    new_entry.pause_events = kw_video_events['pause_events']
                    new_entry.change_speed_events = kw_video_events['change_speed_events']
                    new_entry.seek_from_events = kw_video_events['seek_from_events']
                    new_entry.seek_to_events = kw_video_events['seek_to_events']                    
                except VideoEvents.DoesNotExist:
                    new_entry = VideoEvents(**kw_video_events)                
                new_entry.save()
 
    else:
        pass
    
############################# VIDEO EVENTS ###############################
 

# Given a video descriptor returns ORDERED the video intervals a student has seen
# A timestamp of the interval points is also recorded.
def find_video_intervals(student, video_module_id):
    INVOLVED_EVENTS = [
        'play_video',
        'seek_video',
    ]
    #event flags to check for duplicity
    play_flag = False # True: last event was a play_videoid
    seek_flag = False # True: last event was a seek_video
    saved_video_flag = False # True: last event was a saved_video_position
    
    interval_start = []
    interval_end = []
    vid_start_time = [] # timestamp for interval_start
    vid_end_time = []   # timestamp for interval_end
    
    iter_video_module_id = to_iterable_module_id(video_module_id)
    #shortlist criteria
    str1 = ';_'.join(x for x in iter_video_module_id if x is not None)
    #DEPRECATED TAG i4x                str2 = ''.join([video_module_id.DEPRECATED_TAG,':;_;_',str1])
    cond1   = Q(event_type__in=INVOLVED_EVENTS, event__contains=video_module_id.html_id())
    cond2_1 = Q(event_type__contains = str1)
    cond2_2 = Q(event_type__contains='save_user_state', event__contains='saved_video_position')
    shorlist_criteria = Q(username=student) & (cond1 | (cond2_1 & cond2_2))
    
    events = TrackingLog.objects.filter(shorlist_criteria)
    if events.count() <= 0:
        # return description: [interval_start, interval_end, vid_start_time, vid_end_time]
        # return list types: [int, int, datetime.date, datetime.date]
        return [0], [0], [], []
    #guarantee the list of events starts with a play_video
    while events[0].event_type != 'play_video':
        events = events[1:]
        if len(events) < 2:
            return [0], [0], [], []
    for event in events:
        if event.event_type == 'play_video':
            if play_flag: # two consecutive play_video events. Second is the relevant one (loads saved_video_position).
                interval_start.pop() #removes last element
                vid_start_time.pop()
            if not seek_flag:
                interval_start.append(eval(event.event)['currentTime'])
                vid_start_time.append(event.time)
            play_flag = True
            seek_flag = False
            saved_video_flag = False
        elif event.event_type == 'seek_video':
            if seek_flag:
                interval_start.pop()
                vid_start_time.pop()
            elif play_flag:
                interval_end.append(eval(event.event)['old_time'])
                vid_end_time.append(event.time)
            interval_start.append(eval(event.event)['new_time'])
            vid_start_time.append(event.time)
            play_flag = False
            seek_flag = True
            saved_video_flag = False
        else: # .../save_user_state
            if play_flag:
                interval_end.append(hhmmss_to_secs(eval(event.event)['POST']['saved_video_position'][0]))
                vid_end_time.append(event.time)
            elif seek_flag:
                interval_start.pop()
                vid_start_time.pop()
            play_flag = False
            seek_flag = False
            saved_video_flag = True
    interval_start = [int(math.floor(val)) for val in interval_start]
    interval_end   = [int(math.floor(val)) for val in interval_end]
    #remove empty intervals (start equals end) and guarantee start < end 
    interval_start1 = []
    interval_end1 = []
    vid_start_time1 = []
    vid_end_time1 = []
    for start_val, end_val, start_time, end_time in zip(interval_start, interval_end, vid_start_time, vid_end_time):
        if start_val < end_val:
            interval_start1.append(start_val)
            interval_end1.append(end_val)
            vid_start_time1.append(start_time)
            vid_end_time1.append(end_time)
        elif start_val > end_val: # case play from video end
            interval_start1.append(0)
            interval_end1.append(end_val)
            vid_start_time1.append(start_time)
            vid_end_time1.append(end_time)            
    # sorting intervals
    if len(interval_start1) <= 0:
        return [0], [0], [], []
    [interval_start, interval_end, vid_start_time, vid_end_time] = zip(*sorted(zip(interval_start1, interval_end1, vid_start_time1, vid_end_time1)))
    interval_start = list(interval_start)
    interval_end = list(interval_end)
    vid_start_time = list(vid_start_time)
    vid_end_time = list(vid_end_time)
    
    # return list types: [int, int, datetime.date, datetime.date]
    return interval_start, interval_end, vid_start_time, vid_end_time    
    

# Obtain list of events relative to videos and their relative position within the video
# For a single student
# CT Current time
# Return format: [[CTs for play], [CTs for pause], [CTs for speed changes], [old_time list], [new_time list]]
# Returns None if there are no events matching criteria
def get_video_events(student, video_module_id):
  
    INVOLVED_EVENTS = [
        'play_video',
        'pause_video',
        'speed_change_video',
        'seek_video'
    ]

    #shortlist criteria
    cond1 = Q(event_type__in=INVOLVED_EVENTS, event__contains=video_module_id.html_id())
    shorlist_criteria = Q(username=student) & cond1
    
    events = TrackingLog.objects.filter(shorlist_criteria)
    if events.count() == 0:
        return None
    
    # List of lists. A list for every event type containing the video relative time    
    events_times = []
    for event in INVOLVED_EVENTS + ['list for seek new_time']:
        events_times.append([])
        
    for event in events:
        currentTime = get_current_time(event)
        events_times[INVOLVED_EVENTS.index(event.event_type)].append(currentTime[0])
        if len(currentTime) > 1: # save new_time for seek_video event
            events_times[-1].append(currentTime[1])
    
    return events_times

    
##########################################################################
############################ PROBLEM EVENTS ##############################
##########################################################################  
    

# Computes the time a student has dedicated to a problem in seconds
#TODO Does it make sense to change the resolution to minutes?
# Returns also daily time spent on a problem by the user
def time_on_problem(student, problem_module_id):
    INVOLVED_EVENTS = [
        'seq_goto',
        'seq_prev',
        'seq_next',
        'page_close'
    ]
    interval_start = []
    interval_end = []
    
    iter_problem_module_id = to_iterable_module_id(problem_module_id)
    #shortlist criteria
    str1 = ';_'.join(x for x in iter_problem_module_id if x is not None)
    #DEPRECATED TAG i4x                str2 = ''.join([problem_module_id.DEPRECATED_TAG,':;_;_',str1])
    cond1 = Q(event_type__in=INVOLVED_EVENTS)
    cond2 = Q(event_type__contains = str1) & Q(event_type__contains = 'problem_get')
    shorlist_criteria = Q(username=student) & (cond1 | cond2)
    
    events = TrackingLog.objects.filter(shorlist_criteria)
    if events.count() <= 0:
        # return description: [problem_time, days, daily_time]
        # return list types: [int, datetime.date, int]
        return 0, [], 0
    
    # Ensure pairs problem_get - INVOLVED_EVENTS (start and end references)
    event_pairs = []
    # Flag to control the pairs. get_problem = True means get_problem event expected
    get_problem = True
    for event in events:
        if get_problem: # looking for a get_problem event
            if re.search('problem_get$',event.event_type) is not None:
                event_pairs.append(event.time)
                get_problem = False
        else:# looking for an event in INVOLVED_EVENTS
            if event.event_type in INVOLVED_EVENTS: 
                event_pairs.append(event.time)
                get_problem = True
    problem_time = 0
    """
    if len(event_pairs) > 0:
        for index in range(0, len(event_pairs), 2):
    """
    i = 0
    while i < len(event_pairs) - 1:        
        time_fraction = (event_pairs[i+1] - event_pairs[i]).total_seconds()
        #TODO Bound time fraction to a reasonable value. Here 2 hours. What would be a reasonable maximum?
        time_fraction = 2*60*60 if time_fraction > 2*60*60 else time_fraction
        problem_time += time_fraction
        i += 2
            
    # Daily info
    days = [event_pairs[0].date()] if len(event_pairs) >= 2 else []
#    for event in event_pairs:
#        days.append(event.date())
    daily_time = [0]
    i = 0
    while i < len(event_pairs) - 1:
        if days[-1] == event_pairs[i].date(): # another interval to add to the same day
            if event_pairs[i+1].date() == event_pairs[i].date(): # the interval belongs to a single day
                daily_time[-1] += (event_pairs[i+1] - event_pairs[i]).total_seconds()
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10. 
                daily_time[-1] += 24*60*60 - event_pairs[i].hour*60*60 - event_pairs[i].minute*60 - event_pairs[i].second
                days.append(event_pairs[i+1].date())
                daily_time.append(event_pairs[i+1].hour*60*60 + event_pairs[i+1].minute*60 + event_pairs[i+1].second)
        else:
            days.append(event_pairs[i].date())
            daily_time.append(0)
            if event_pairs[i+1].date() == event_pairs[i].date(): # the interval belongs to a single day
                daily_time[-1] += (event_pairs[i+1] - event_pairs[i]).total_seconds()
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10.
                daily_time[-1] += 24*60*60 - event_pairs[i].hour*60*60 - event_pairs[i].minute*60 - event_pairs[i].second
                days.append(event_pairs[i+1].date())
                daily_time.append(event_pairs[i+1].hour*60*60 + event_pairs[i+1].minute*60 + event_pairs[i+1].second)            
        i += 2
    return problem_time, days, daily_time

# Get info for Video time watched chart
def get_module_consumption(username, course_id, module_type, visualization):
  
    #shortlist criteria
    shortlist = Q(student=username, course_key=course_id, module_type = module_type)
    consumption_modules = ConsumptionModule.objects.filter(shortlist)
    module_names = []
    total_times = []    
    video_percentages = []
    for consumption_module in consumption_modules:
        module_names.append(consumption_module.display_name)
        
        if (visualization == 'total_time_vid_prob'):   
            # From minutes to seconds              
            total_times.append(round(truediv(consumption_module.total_time,60),2))
            
        elif (visualization == 'video_progress'):                           
            video_percentages.append(consumption_module.percent_viewed)            
            if(username == '#average'):
                # Dividing total time between the number of students to get avg time on video which is used in video progress
                total_times.append(int(round(truediv(consumption_module.total_time,len(CourseEnrollment.users_enrolled_in(course_id))),0)))
            else:
                total_times.append(consumption_module.total_time)
            
    if sum(total_times) <= 0:
        total_times = []
        video_percentages = []
  
    return module_names, total_times, video_percentages


# Get info for Daily time on video and problems chart
# Daily time spent on video and problem resources
def get_daily_consumption(username, course_id, module_type):

    #shortlist criteria
    #shortlist = Q(student=username, course_key=course_id, module_type = module_type)
    try:
        daily_consumption = DailyConsumption.objects.get(student=username, course_key=course_id, module_type = module_type)
        jsonDec = json.decoder.JSONDecoder()
        days = jsonDec.decode(daily_consumption.dates)
        # From minutes to seconds
        daily_time = jsonDec.decode(daily_consumption.time_per_date)
        daily_time_min =  []
        for day_time in daily_time:
            daily_time_min.append(truediv(day_time, 60))        
    except DailyConsumption.DoesNotExist:
        days, daily_time_min = [], []
    """
    for daily_consumption in daily_consumptions:
        days.append(jsonDec.decode(daily_consumption.dates))
        daily_time.append(jsonDec.decode(daily_consumption.time_per_date))
    """
    return days, daily_time_min


# Get info for Video events dispersion within video length chart
# At what time the user did what along the video?
def get_video_events_info(username, video_id):
  
    if username == '#average':
        shortlist = Q(module_key = video_id)
    else:
        shortlist = Q(student=username, module_key = video_id)
    video_events = VideoEvents.objects.filter(shortlist)
    jsonDec = json.decoder.JSONDecoder()
    events_times = [[],[],[],[],[]]
    for user_video_events in video_events:
        events_times[0] += jsonDec.decode(user_video_events.play_events)
        events_times[1] += jsonDec.decode(user_video_events.pause_events)
        events_times[2] += jsonDec.decode(user_video_events.change_speed_events)
        events_times[3] += jsonDec.decode(user_video_events.seek_from_events)
        events_times[4] += jsonDec.decode(user_video_events.seek_to_events)
  
    if events_times != [[],[],[],[],[]]:
        scatter_array = video_events_to_scatter_chart(events_times)
    else:
        scatter_array = json.dumps(None)
    
    return scatter_array
    

# Get info for Repetitions per video intervals chart
# How many times which video intervals have been viewed?
def get_user_video_intervals(username, video_id):

    try:
        video_intervals = VideoIntervals.objects.get(student=username, module_key = video_id)
    except VideoIntervals.DoesNotExist:
        return json.dumps(None)
    
    jsonDec = json.decoder.JSONDecoder()
    hist_xaxis = jsonDec.decode(video_intervals.hist_xaxis)
    hist_yaxis = jsonDec.decode(video_intervals.hist_yaxis)
    num_gridlines = 0
    vticks = []
    
    # Interpolation to represent one-second-resolution intervals
    if sum(hist_yaxis) > 0:
        maxRepetitions = max(hist_yaxis)
        num_gridlines = maxRepetitions + 1 if maxRepetitions <= 3 else 5
        vticks = determine_repetitions_vticks(maxRepetitions)
        ordinates_1s = []
        abscissae_1s = list(range(0,hist_xaxis[-1]+1))
        #ordinates_1s.append([])
        for j in range(0,len(hist_xaxis)-1):
            while len(ordinates_1s) <= hist_xaxis[j+1]:
                ordinates_1s.append(hist_yaxis[j])
                
        # array to be used in the arrayToDataTable method of Google Charts
        # actually a list of lists where the first one represent column names and the rest the rows
        video_intervals_array = [['Time (s)', 'Times']]
        for abscissa_1s, ordinate_1s in zip(abscissae_1s, ordinates_1s):
            video_intervals_array.append([str(abscissa_1s), ordinate_1s])
    else:
        video_intervals_array = None
        
    interval_chart_data = {
        'video_intervals_array': video_intervals_array,
        'num_gridlines': num_gridlines,
        'vticks': vticks,
    }    
    
    return json.dumps(interval_chart_data)