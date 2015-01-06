from edxmako.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django_future.csrf import ensure_csrf_cookie
from django.contrib.auth.models import User
from django.http import HttpResponse
import logging
from django.utils import simplejson
from django.db.models import Q
from learning_analytics.analytics import to_iterable_module_id
from track.backends.django import TrackingLog
import math, re

from json import dumps
import gdata.youtube
import gdata.youtube.service
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.locator import CourseLocator, BlockUsageLocator
from opaque_keys.edx.locations import Location, SlashSeparatedCourseKey
from operator import truediv

from analytics import (get_DB_sort_course_homework, 
                       get_DB_course_spent_time, 
                       get_DB_student_grades, 
                       get_DB_course_section_accesses,
                       get_DB_course_video_problem_progress)
from analytics_jose import get_DB_time_schedule
from data import get_course_key, get_course_module, get_course_students, get_course_grade_cutoff

from courseware.access import has_access
from courseware.masquerade import setup_masquerade
from courseware.models import StudentModule
from student.models import CourseEnrollment
from courseware.courses import get_course_with_access, get_studio_url
from courseware.views import fetch_reverify_banner_info



from models import *
# Celery here acts as a simulator.
from celeryHector import update_visualization_data, clean_xinsider_tables
from data_querying import *
from data_processing import *


VISUALIZATIONS_ID = {'LA_course_sort_students': 0,
                     'LA_student_grades': 1,
                     'LA_chapter_time': 2,
                     'LA_course_accesses': 3,
                     'LA_time_schedule': 4,
                     'LA_vid_prob_prog': 5,}

# Constants for student_id
ALL_STUDENTS = -1
PROF_GROUP = -2
PASS_GROUP = -3
FAIL_GROUP = -4

# Create your views here.

@login_required
@ensure_csrf_cookie
def index(request, course_id):
   
    # Request data
    course_key = get_course_key(course_id)
    course = get_course_module(course_key)
    user = request.user
    staff_access = has_access(request.user, 'staff', course)
    instructor_access = has_access(request.user, 'instructor', course)
    masq = setup_masquerade(request, staff_access)  # allow staff to toggle masquerade on info page
    studio_url = get_studio_url(course, 'course_info')
    reverifications = fetch_reverify_banner_info(request, course_key)
    
    #course = get_course_with_access(request.user, action='load', course_key=course_key, depth=None, check_if_enrolled=False)
    
    # Proficiency and pass limit
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit
    
    usernames_in = []
    for student in CourseEnrollment.users_enrolled_in(course_key):
        usernames_in.append(student.username.encode('utf-8'))
              
  
    # Data for visualization in JSON
    user_for_charts = '#average' if staff_access else user
    kwargs = {
        'qualifiers': {'category': 'video', },
    }
          
    # This returns video descriptors in the order they appear on the course
    video_descriptors = videos_problems_in(course)[0]
      
    video_ids_str = []
    course_video_names = []
    for descriptor in video_descriptors:
        video_ids_str.append((course_key.make_usage_key('video', descriptor.location.name))._to_string())
        course_video_names.append(descriptor.display_name_with_default)
  
    if len(video_descriptors) > 0:
        first_video_id = course_key.make_usage_key('video', video_descriptors[0].location.name)
          
        # Video progress visualization. Video percentage seen total and non-overlapped.    
        video_names, all_video_time, video_percentages = get_module_consumption(user_for_charts, course_key, 'video')
        column_headers = ['Video', 'Non-overlapped (%)', 'Total vs. video length (%)']
        video_prog_json = ready_for_arraytodatatable(column_headers, video_names, video_percentages, all_video_time)
   
        # Time spent on every video resource
        column_headers = ['Video', 'Time watched']
        video_distrib_json = ready_for_arraytodatatable(column_headers, video_names, all_video_time)
  
        # Video events dispersion within video length
        scatter_array = get_video_events_info(user_for_charts, first_video_id)    
  
        # Repetitions per video intervals
        user_for_vid_intervals = '#class_total_times' if user_for_charts == '#average' else user_for_charts
        video_intervals_array = get_user_video_intervals(user_for_vid_intervals, first_video_id)        
          
    # Case no videos in course
    else:
        video_names = None
        video_prog_json = simplejson.dumps(None)
        video_distrib_json = simplejson.dumps(None)
        scatter_array = simplejson.dumps(None)
        video_intervals_array = simplejson.dumps(None)
          
    # Time spent on every problem resource
    problem_names, time_x_problem = get_module_consumption(user_for_charts, course_key, 'problem')[0:2]    
    column_headers = ['Problem', 'Time on problem']
    problem_distrib_json = ready_for_arraytodatatable(column_headers, problem_names, time_x_problem)
      
    # Daily time spent on video and/or problem resources
    video_days, video_daily_time = get_daily_consumption(user_for_charts, course_key, 'video')
    problem_days, problem_daily_time = get_daily_consumption(user_for_charts, course_key, 'problem')    
    vid_and_prob_daily_time = join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time) 
    
    #Analytics visualizations
    if staff_access or instructor_access:
        # Instructor access
        # Sort homework
        std_sort = get_DB_sort_course_homework(course_key)
        # Chapter time
        cs, st = get_DB_course_spent_time(course_key, student_id=ALL_STUDENTS)
        students_spent_time = chapter_time_to_js(cs, st)
        students_grades = get_DB_student_grades(course_key, student_id=ALL_STUDENTS)
        cs, sa = course_accesses = get_DB_course_section_accesses(course_key, student_id=ALL_STUDENTS)
        students_course_accesses = course_accesses_to_js(cs, sa)
        students_prob_vid_progress = get_DB_course_video_problem_progress(course_key, student_id=ALL_STUDENTS)
        students_time_schedule = get_DB_time_schedule(course_key, student_id=ALL_STUDENTS)
            
        
        context = {'course': course,
                   'request': request,
                   'user': user,
                   'staff_access': staff_access,
                   'instructor_access': instructor_access,
                   'masquerade': masq,
                   'studio_url': studio_url,
                   'reverifications': reverifications,
                   'course_id': course_id,
                   'students': students_to_js(get_course_students(course_key)),
                   'visualizations_id': VISUALIZATIONS_ID,
                   'std_grades_dump': dumps(students_grades),
                   'sort_std_dump': dumps(std_sort),
                   'time_dump': dumps(students_spent_time),
                   'accesses_dump': dumps(students_course_accesses),
                   'std_time_schedule_dumb': dumps(students_time_schedule),
                   'vid_prob_prog_dump': dumps(students_prob_vid_progress),
                   'pass_limit': pass_limit,
                   'prof_limit': proficiency_limit,
                   'usernames_in' : usernames_in,
                   'video_names' : course_video_names,
                   'video_ids' : video_ids_str,
                   'video_prog_json' : video_prog_json,
                   'video_distrib_json' : video_distrib_json,
                   'problem_distrib_json' : problem_distrib_json,
                   'video_intervals_array' : video_intervals_array,
                   'vid_and_prob_daily_time' : vid_and_prob_daily_time,
                   'scatter_array' : scatter_array, }
    else:
        # Student access
        
        # Chapter time
        cs, st = get_DB_course_spent_time(course_key, user.id)
        student_spent_time = chapter_time_to_js(cs, st)
        students_grades = get_DB_student_grades(course_key, user.id)
        cs, sa = course_accesses = get_DB_course_section_accesses(course_key, user.id)
        student_course_accesses = course_accesses_to_js(cs, sa)
        student_time_schedule = get_DB_time_schedule(course_key, user.id)
        student_prob_vid_progress = get_DB_course_video_problem_progress(course_key, user.id)
        
        context = {'course': course,
                   'request': request,
                   'user': user,
                   'staff_access': staff_access,
                   'instructor_access': instructor_access,
                   'masquerade': masq,
                   'studio_url': studio_url,
                   'reverifications': reverifications,
                   'course_id': course_id,
                   'students': students_to_js([user]),
                   'std_grades_dump': dumps(students_grades),
                   'sort_std_dump': None,
                   'time_dump': dumps(student_spent_time),
                   'accesses_dump': dumps(student_course_accesses),
                   'std_time_schedule_dumb': dumps(student_time_schedule),
                   'vid_prob_prog_dump': dumps(student_prob_vid_progress),
                   'pass_limit': pass_limit,
                   'prof_limit': proficiency_limit,
                   'usernames_in' : usernames_in,
                   'video_names' : course_video_names,
                   'video_ids' : video_ids_str,
                   'video_prog_json' : video_prog_json,
                   'video_distrib_json' : video_distrib_json,
                   'problem_distrib_json' : problem_distrib_json,
                   'video_intervals_array' : video_intervals_array,
                   'vid_and_prob_daily_time' : vid_and_prob_daily_time,
                   'scatter_array' : scatter_array, }
        
    return render_to_response('learning_analytics/learning_analytics.html', context)    


@login_required
@ensure_csrf_cookie
def chart_update(request):
    results = {'success' : False}
    chart_info_json = dumps(results)
    if request.method == u'GET':
        GET = request.GET
        course_key = get_course_key(GET[u'course_id'])
        user_id = GET[u'user_id']
        chart = int(GET[u'chart'])
        if chart == VISUALIZATIONS_ID['LA_chapter_time']:
            cs, st = get_DB_course_spent_time(course_key, student_id=user_id)
            student_spent_time = chapter_time_to_js(cs, st)
            chart_info_json = dumps(student_spent_time)
        elif chart == VISUALIZATIONS_ID['LA_course_accesses']:
            cs, sa = get_DB_course_section_accesses(course_key, student_id=user_id)
            student_course_accesses = course_accesses_to_js(cs, sa)
            chart_info_json = dumps(student_course_accesses)
        elif chart == VISUALIZATIONS_ID['LA_student_grades']:
            students_grades = get_DB_student_grades(course_key, student_id=user_id)
            chart_info_json = dumps(students_grades)
        elif chart == VISUALIZATIONS_ID['LA_time_schedule']:
            student_time_schedule = get_DB_time_schedule(course_key, student_id=user_id)
            chart_info_json = dumps(student_time_schedule)
        elif chart == VISUALIZATIONS_ID['LA_vid_prob_prog']:
            student_prob_vid_progress = get_DB_course_video_problem_progress(course_key, student_id=user_id)
            chart_info_json = dumps(student_prob_vid_progress)
    
    return HttpResponse(chart_info_json, mimetype='application/json')

def chapter_time_to_js(course_struct, students_time):
    """
    Formats time chapters data to send it to a javascript script
    """
    result = {}
    for st_id in students_time.keys():
        result[st_id] = []
        for chapter in course_struct:
            chapt_data = {'name': chapter['name'],
                          'total_time': students_time[st_id][chapter['id']]['time_spent']}
            graded_time = 0
            ungraded_time = 0
            for sequential in chapter['sequentials']:
                if sequential['graded']:
                    graded_time = (graded_time + 
                                   students_time[st_id][chapter['id']]['sequentials'][sequential['id']]['time_spent'])
                else:
                    ungraded_time = (ungraded_time + 
                                     students_time[st_id][chapter['id']]['sequentials'][sequential['id']]['time_spent'])
            
            chapt_data['graded_time'] = graded_time
            chapt_data['ungraded_time'] = ungraded_time
            result[st_id].append(chapt_data)
            
    return result


def students_to_js(students_user):
    result = []
    for user in students_user:
        result.append({'id':user.id, 'name':user.username })
    return result


def course_accesses_to_js(course_struct, students_course_accesses):
    """
    Formats course accesses data to send it to a javascript script
    """
    result = {}
    for st_id in students_course_accesses.keys():
        result[st_id] = []
        for chapter in course_struct:
            chapt_data = {'name': chapter['name'],
                          'accesses': students_course_accesses[st_id][chapter['id']]['accesses'],
                          'sequentials':[]}
            for sequential in chapter['sequentials']:
                seq_data = {'name': sequential['name'],
                            'accesses': students_course_accesses[st_id][chapter['id']]['sequentials'][sequential['id']]['accesses'],
                            'verticals':[]}
                for vertical in sequential['verticals']:
                    vert_data = {'name': vertical['name'],
                                 'accesses': students_course_accesses[st_id][chapter['id']]['sequentials'][sequential['id']]['verticals'][vertical['id']]['accesses']}
                    seq_data['verticals'].append(vert_data)
                chapt_data['sequentials'].append(seq_data)
            result[st_id].append(chapt_data)
    return result


@login_required
#@ensure_csrf_cookie
# Serve AJAX requests to select information displayed on charts dinamically by course instructors
# request is a Django HttpRequest object
def chart_ajax(request, course_id):

    results = {'success' : False}
    chart_info_json = simplejson.dumps(results)
    course_key = CourseLocator._from_deprecated_string(course_id)
    if request.method == u'GET':
        GET = request.GET
        user_id = GET[u'user_id']
        user_id = request.user if user_id == "" else user_id
        chart = int(GET[u'chart'])
        video_name = GET[u'video']

        chart_info_json = get_info_for_client(user_id, course_key, chart, video_name)
        
    return HttpResponse(chart_info_json, mimetype='application/json')


# Runs the adequate function to respond to the client
# chart: int
# course: course descriptor
def get_info_for_client(user_id, course_id, chart, video_name):
  
    if chart == 1:
        # Video progress visualization. Video percentage seen total and non-overlapped.    
        video_names, all_video_time, video_percentages = get_module_consumption(user_id, course_id, 'video')
        column_headers = ['Video', 'Non-overlapped (%)', 'Total vs. video length (%)']
        chart_info_json = ready_for_arraytodatatable(column_headers, video_names, video_percentages, all_video_time)
    elif chart == 2:
        # Time spent on every video resource
        video_names, all_video_time = get_module_consumption(user_id, course_id, 'video')[0:2]
        column_headers = ['Video', 'Time watched']
        chart_info_json = ready_for_arraytodatatable(column_headers, video_names, all_video_time)
    elif chart == 3:
        # Time spent on every problem resource
        problem_names, time_x_problem = get_module_consumption(user_id, course_id, 'problem')[0:2]    
        column_headers = ['Problem', 'Time on problem']
        chart_info_json = ready_for_arraytodatatable(column_headers, problem_names, time_x_problem)
    elif chart == 4:
        # Repetitions per video intervals
        video_id = BlockUsageLocator._from_string(video_name)
        video_id = Location.from_deprecated_string(video_id._to_deprecated_string())
        chart_info_json = get_user_video_intervals(user_id, video_id)
    elif chart == 5:
        # Daily time spent on video and/or problem resources
        video_days, video_daily_time = get_daily_consumption(user_id, course_id, 'video')
        problem_days, problem_daily_time = get_daily_consumption(user_id, course_id, 'problem')    
        chart_info_json = join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time)          
    elif chart == 6:
        # Video events dispersion within video length
        video_id = BlockUsageLocator._from_string(video_name)
        video_id = Location.from_deprecated_string(video_id._to_deprecated_string())        
        chart_info_json = get_video_events_info(user_id, video_id)         
    else:
        chart_info_json = simplejson.dumps(None)
        
    return chart_info_json
