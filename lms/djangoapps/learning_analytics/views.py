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

from opaque_keys.edx.locations import SlashSeparatedCourseKey
from json import dumps
import gdata.youtube
import gdata.youtube.service
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.locator import BlockUsageLocator
from operator import truediv

from analytics import (get_DB_sort_course_homework, 
                       get_DB_course_spent_time, 
                       get_DB_student_grades, 
                       get_DB_course_section_accesses)
from analytics_jose import get_DB_time_schedule
from data import get_course_key, get_course_module, get_course_students, get_course_grade_cutoff

from courseware.access import has_access
from courseware.masquerade import setup_masquerade
from courseware.models import StudentModule
from student.models import CourseEnrollment
from courseware.courses import get_course_with_access, get_studio_url
from courseware.views import fetch_reverify_banner_info


VISUALIZATIONS_ID = {'LA_course_sort_students': 0,
                     'LA_student_grades': 1,
                     'LA_chapter_time': 2,
                     'LA_course_accesses': 3,
                     'LA_time_schedule': 4,}

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
    
    # Proficiency and pass limit
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit
    
    usernames_in = []
    for student in CourseEnrollment.users_enrolled_in(course_key):
        usernames_in.append(student.username.encode('utf-8'))
        
    # Course Video info
    [video_names, video_module_ids, video_durations] = get_info_videos(course)
    # Student video consumption
    #[video_names, video_percentages, all_video_time] = video_consumption('staff', course)

    # Data for visualization in JSON
    
    user_for_charts = '#average' if staff_access else user
    
    # Video progress visualization. Video percentage seen total and non-overlapped.
    video_prog_json = video_time_data(user_for_charts, course)
    # Time spent on every video resource
    video_distrib_json = video_time_distribution(user_for_charts, course)
    # Time spent on every problem resource
    problem_distrib_json = problem_time_distribution(user_for_charts, course)
    # Daily time spent on video and/or problem resources
    vid_and_prob_daily_time = daily_vid_prob_time(user_for_charts, course)
    # Video events dispersion within video length
    scatter_array = get_video_events_info(user_for_charts, video_module_ids[0], course)
    # Repetitions per video intervals
    user_for_charts = '#class_total_times' if user_for_charts == '#average' else user_for_charts
    video_intervals_array = user_video_intervals(user_for_charts, video_module_ids[0], course)
    video_intervals_array = simplejson.dumps(video_intervals_array) 
    # Analytics visualizations
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
                   'pass_limit': pass_limit,
                   'prof_limit': proficiency_limit,
                    'usernames_in' : usernames_in,
                    'video_names' : video_names,
                    'video_module_ids' : video_module_ids,
                    #'video_percentages' : video_percentages,
                    'video_prog_json' : video_prog_json,
                    'video_distrib_json' : video_distrib_json,
                    'problem_distrib_json' : problem_distrib_json,
                    'video_intervals_array' : video_intervals_array,
                    'vid_and_prob_daily_time' : vid_and_prob_daily_time,
                    'scatter_array' : scatter_array,   }
    else:
        # Student access
        
        # Chapter time
        cs, st = get_DB_course_spent_time(course_key, user.id)
        student_spent_time = chapter_time_to_js(cs, st)
        students_grades = get_DB_student_grades(course_key, user.id)
        cs, sa = course_accesses = get_DB_course_section_accesses(course_key, user.id)
        student_course_accesses = course_accesses_to_js(cs, sa)
        student_time_schedule = get_DB_time_schedule(course_key, user.id)
        
        
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
                   'pass_limit': pass_limit,
                   'prof_limit': proficiency_limit,
                    'usernames_in' : usernames_in,
                    'video_names' : video_names,
                    'video_module_ids' : video_module_ids,
                    #'video_percentages' : video_percentages,
                    'video_prog_json' : video_prog_json,
                    'video_distrib_json' : video_distrib_json,
                    'problem_distrib_json' : problem_distrib_json,
                    'video_intervals_array' : video_intervals_array,
                    'vid_and_prob_daily_time' : vid_and_prob_daily_time,
                    'scatter_array' : scatter_array,  }
        
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
    if request.method == u'GET':
        GET = request.GET
        # CourseDescriptor
        course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
        course = get_course_with_access(request.user, action='load', course_key=course_key, depth=None, check_if_enrolled=False)
        #course = get_course_by_id(GET[u'course_id'], depth=0)
        user_id = GET[u'user_id']
        user_id = request.user if user_id == "" else user_id
        chart = int(GET[u'chart'])
        video_id = GET[u'video']

        chart_info_json = get_info_for_client(user_id, course, chart, video_id)
        
    return HttpResponse(chart_info_json, mimetype='application/json')


# Runs the adequate function to respond to the client
# chart: int
# course: course descriptor
def get_info_for_client(user_id, course, chart, video_id_str):
  
    if chart == 1:
        chart_info_json = video_time_data(user_id, course)
    elif chart == 2:
        chart_info_json = video_time_distribution(user_id, course)
    elif chart == 3:
        chart_info_json = problem_time_distribution(user_id, course)
    elif chart == 4:
        video_id = BlockUsageLocator._from_deprecated_string(video_id_str)
        #video_id = Location(video_id_str)
        chart_info_json = user_video_intervals(user_id, video_id, course)
        chart_info_json = simplejson.dumps(chart_info_json)
    elif chart == 5:
        chart_info_json = daily_vid_prob_time(user_id, course)
    elif chart == 6:
        video_id = BlockUsageLocator._from_deprecated_string(video_id_str)
        #video_id = Location(video_id_str)
        chart_info_json = get_video_events_info(user_id, video_id, course)
    else:
        chart_info_json = simplejson.dumps(None)
    
    return chart_info_json


# Functions responsible for data to build the charts

# Get info for Repetitions per video intervals chart
# How many times which video intervals have been seen?
def user_video_intervals(user_id, video_module_id, course):

    video_descriptor = modulestore().get_item(video_module_id)
    youtube_id = video_descriptor.__dict__['_field_data_cache']['youtube_id_1_0'].encode('utf-8')
    video_duration = float(id_to_length(youtube_id))
    
    hist_xaxis, hist_yaxis = video_histogram_info(user_id, video_module_id, video_duration, course)
    
    # Interpolation to represent one-second-resolution intervals
    if sum(hist_yaxis) > 0:
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
        
    return video_intervals_array


# Get info for Video events dispersion within video length chart
# At what time the user did what along the video?
def get_video_events_info(user_id, video_module_id, course_descriptor):

    if user_id == '#average':
        events_times = get_class_video_events(course_descriptor, video_module_id)
    else:
        events_times = get_video_events(user_id, video_module_id)
    if events_times is not None:
        scatter_array = video_events_to_scatter_chart(events_times)
    else:
        scatter_array = simplejson.dumps(None)
    
    return scatter_array


# Get info for Daily time on video and problems chart
# Daily time spent on video and problem resources
def daily_vid_prob_time(user_id, course_descriptor):

    if user_id == '#average':
        [problem_days, problem_daily_time] = class_time_on_problems(course_descriptor)
        [video_days, video_daily_time] = class_time_on_videos(course_descriptor)        
    else:
        [problem_days, problem_daily_time] = time_on_problems(user_id, course_descriptor)
        [video_days, video_daily_time] = daily_time_on_videos(user_id, course_descriptor)

    vid_and_prob_daily_time = join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time)
    
    return vid_and_prob_daily_time


# Get info for Problem time distribution chart
# Time spent on every problem resource
def problem_time_distribution(user_id, course_descriptor):

    if user_id == '#average':
        [problem_names, time_x_problem] = avg_problem_consumption(course_descriptor)
    else:
        [problem_names, time_x_problem] = problem_consumption(user_id, course_descriptor)
    
    if time_x_problem == []:
        return simplejson.dumps(None) 
    column_headers = ['Problem', 'Time on problem']
    problem_distrib_json = ready_for_arraytodatatable(column_headers, problem_names, time_x_problem)
    
    return problem_distrib_json


# Returns problem consumption in the form of problem names 
# and total time spent per problem for the class average
def avg_problem_consumption(course):

    problem_names = []
    accum_problem_time = []
    usernames_in = []
    for student in CourseEnrollment.users_enrolled_in(course.id):
        usernames_in.append(student.username.encode('utf-8'))
    for i in range(0, len(usernames_in)):
        problem_names, time_x_problem = problem_consumption(usernames_in[i], course)
        if time_x_problem == []:
            continue        
        if accum_problem_time == []:
            accum_problem_time = time_x_problem
        else:
            for j in range(0, len(accum_problem_time)):
                accum_problem_time[j] += time_x_problem[j]
    if time_x_problem != []:                
        for i in range(0, len(problem_names)):
            accum_problem_time[i] = truediv(accum_problem_time[i],len(usernames_in))
    
    return problem_names, accum_problem_time


# Returns problem consumption in the form of problem names 
# and total time spent per problem for a certain user
def problem_consumption(user, course):
    # Time dedicated to problems
    [chapters_w_problems, problems_per_chapter, problem_descriptors] = list_problem_descriptors(course)
    time_x_problem = []
    problem_names = []
    for problem in problem_descriptors:
        time_x_problem.append(time_on_problem(user, problem.location)[0])
        problem_names.append(unicode(problem.display_name_with_default))
    if sum(time_x_problem) <= 0:
        time_x_problem = []
    
    # Code to compute problem time spent on a chapter basis
    # Currently unused
    """
    chapter_problem_time = []
    total_counter = 0
    for chapter in range(0,len(chapters_w_problems)):
        chapter_problem_time.append(0)
        part_counter = problems_per_chapter[chapter]
        while part_counter > 0:
            chapter_problem_time[chapter] += time_x_problem[total_counter]
            total_counter += 1
            part_counter -= 1  
    """
    return problem_names, time_x_problem


# Get info for Video time distribution chart
# Time spent on every video resource
def video_time_distribution(user_id, course_descriptor):

    if user_id == '#average':
        [video_names, ignored, all_video_time] = avg_video_consumption(course_descriptor)
    else:
        [video_names, ignored, all_video_time] = video_consumption(user_id, course_descriptor)
        
    column_headers = ['Video', 'Time watched']
    video_distrib_json = ready_for_arraytodatatable(column_headers, video_names, all_video_time)
    
    return video_distrib_json


# Get info for Video time watched chart
def video_time_data(user_id, course_descriptor):

    if user_id == '#average':
        [video_names, video_percentages, all_video_time] = avg_video_consumption(course_descriptor, percentage_flag=True)
    else:
        [video_names, video_percentages, all_video_time] = video_consumption(user_id, course_descriptor, percentage_flag=True)
        
    column_headers = ['Video', 'Non-overlapped (%)', 'Total vs. video length (%)']    
    video_prog_json = ready_for_arraytodatatable(column_headers, video_names, video_percentages, all_video_time)
    
    return video_prog_json


# Returns video consumption in the form of video names, percentages
# per video seen and total time spent per video for the class average
def avg_video_consumption(course, percentage_flag=False):
  
    una_prueba = []
    video_names = []
    accum_video_percentages = []
    accum_all_video_time = []
    usernames_in = []
    for student in CourseEnrollment.users_enrolled_in(course.id):
        usernames_in.append(student.username.encode('utf-8'))
    for i in range(0, len(usernames_in)):
        print("\n\n" + usernames_in[i])
        [video_names, video_percentages, all_video_time] = video_consumption(usernames_in[i], course, percentage_flag)
        print(repr(video_percentages))
        una_prueba.append(video_percentages)
        print(repr(una_prueba) + "\n\n")
        if video_percentages == []:
            continue
        if accum_video_percentages == []:
            accum_video_percentages = video_percentages
            accum_all_video_time = all_video_time
            print("accum_video_percentages:" + repr(accum_video_percentages))
            print("accum_all_video_time" + repr(accum_all_video_time) + "\n\n")
        else:
            for j in range(0, len(accum_all_video_time)):
                print("len(accum_all_video_time):" + repr(len(accum_all_video_time)))
                accum_video_percentages[j] += video_percentages[j]
                accum_all_video_time[j] += all_video_time[j]
                print("accum_video_percentages:" + repr(accum_video_percentages))
                print("accum_all_video_time" + repr(accum_all_video_time) + "\n\n")
    for i in range(0, len(video_names)):
        accum_video_percentages[i] = truediv(accum_video_percentages[i],len(usernames_in))
        accum_all_video_time[i] = truediv(accum_all_video_time[i],len(usernames_in))
    
    return [video_names, accum_video_percentages, accum_all_video_time]
    

# Returns video consumption in the form of video names, percentages
# per video seen and total time spent per video for a certain user
# video_percentages is always a %
# all_video_time is a % if percentage_flag=True otherwise is an absolute value in seconds
def video_consumption(user, course, percentage_flag=False):

    [video_names, video_module_ids, video_durations] = get_info_videos(course)
    
    # Non-overlapped video time
    stu_video_seen = []
    # Video length seen based on tracking-log events (best possible measure)
    for video_module_id in video_module_ids:
        [aux_start, aux_end] = video_len_watched(user,video_module_id)
        interval_sum = 0
        for start, end in zip(aux_start,aux_end):
            interval_sum += end - start
        stu_video_seen.append(interval_sum)
        
    if sum(stu_video_seen) <= 0:
        return [], [], []
        
    video_percentages = map(truediv, stu_video_seen, video_durations)
    video_percentages = [val*100 for val in video_percentages]
    video_percentages = [int(round(val,0)) for val in video_percentages]
    # Ensure artificially percentages do not surpass 100%, which
    # could happen slightly from the 1s adjustment in id_to_length function
    for i in range(0,len(video_percentages)):
        if video_percentages[i] > 100:
            video_percentages[i] = 100
    
    # Total video time seen
    all_video_time = []
    for video, duration in zip(video_module_ids, video_durations):
        video_time = 0
        interval_start, interval_end = find_video_intervals(user, video)[0:2]
        for start, end in zip(interval_start, interval_end):
            video_time += end - start
        value = int(round(truediv(video_time, duration)*100,0)) if percentage_flag else video_time
        all_video_time.append(value)
  
    return video_names, video_percentages, all_video_time


# Returns info of videos in course.
# Specifically returns their names, durations and module_ids
def get_info_videos(course):
    video_descriptors = list_video_descriptors(course)
    video_names = []
    youtube_ids = []
    video_durations = []
    video_module_ids = []
    
    for video_descriptor in video_descriptors:
        video_names.append(unicode(video_descriptor.display_name_with_default)) #__dict__['_field_data_cache']['display_name'].encode('utf-8'))
        youtube_ids.append(video_descriptor.__dict__['_field_data_cache']['youtube_id_1_0'].encode('utf-8'))
        video_module_ids.append(video_descriptor.location)
        
    for youtube_id in youtube_ids:
        video_durations.append(float(id_to_length(youtube_id))) #float useful for video_percentages to avoid precision loss
        
    return [video_names, video_module_ids, video_durations]
    
    
# Convert a time in format HH:MM:SS to seconds
def hhmmss_to_secs(hhmmss):
    if re.match('[0-9]{2}(:[0-5][0-9]){2}', hhmmss) is None:
        return 0
    else:
        split = hhmmss.split(':')
        hours = int(split[0])
        minutes = int(split[1])
        seconds = int(split[2])
        return hours*60*60+minutes*60+seconds


# Retrieve video-length via Youtube given its ID
def id_to_length(youtube_id):
  
    yt_service = gdata.youtube.service.YouTubeService()

    # Turn on HTTPS/SSL access.
    # Note: SSL is not available at this time for uploads.
    yt_service.ssl = True

    entry = yt_service.GetYouTubeVideoEntry(video_id=youtube_id)

    # Maximum video position registered in the platform differs around 1s
    # wrt youtube duration. Thus 1 is subtracted to compensate.
    return eval(entry.media.duration.seconds) - 1


# Probably this function should live in course_module.py
# Given a course_descriptor returns a list of the videos in the course
# Probably this function should be merged with list_problem_descriptors in a single list_descriptors
def list_video_descriptors(course_descriptor):
    video_descriptors = []
    for chapter in course_descriptor.get_children():
        for sequential_or_videosequence in chapter.get_children():
            for vertical_or_problemset in sequential_or_videosequence.get_children():
                for content in vertical_or_problemset.get_children():
                    if content.location.category == unicode('video'):
                        video_descriptors.append(content)
    return video_descriptors
    
    
# Probably this function should live in course_module.py
# Given a course_descriptor returns a list of the problems in the course
# Probably this function should be merged with list_video_descriptors in a single list_descriptors
def list_problem_descriptors(course_descriptor):
    problem_descriptors = []
    # Name of chapters with problems
    chapters_w_problems = []
    problems_per_chapter = []
    # Counter for number of problems in chapter
    problem_counter = 0
    for chapter in course_descriptor.get_children():
        for sequential_or_videosequence in chapter.get_children():
            for vertical_or_problemset in sequential_or_videosequence.get_children():
                for content in vertical_or_problemset.get_children():
                    if content.location.category == unicode('problem'):
                        problem_descriptors.append(content)
                        problem_counter += 1
        if problem_counter > 0:
            chapters_w_problems.append(unicode(chapter.display_name_with_default))
            problems_per_chapter.append(problem_counter)
        problem_counter = 0
    return [chapters_w_problems, problems_per_chapter, problem_descriptors]


# Returns info to represent a histogram with video intervals watched    
def video_histogram_info(user_id, video_module_id, video_duration, course):

    CLASS_AGGREGATES = ['#class_total_times', '#one_stu_one_time']
    if user_id in CLASS_AGGREGATES:
        usernames_in = []
        for student in CourseEnrollment.users_enrolled_in(course.id):
            usernames_in.append(student.username.encode('utf-8'))
        interval_start = []
        interval_end = []
        for username_in in usernames_in:
          if user_id == '#class_total_times':
              startings, endings = find_video_intervals(username_in, video_module_id)[0:2]          
          elif user_id == '#one_stu_one_time':
              startings, endings = video_len_watched(username_in, video_module_id)
          interval_start = interval_start + startings
          interval_end = interval_end + endings
        # sorting intervals
        interval_start, interval_end = zip(*sorted(zip(interval_start, interval_end)))
        interval_start = list(interval_start)
        interval_end = list(interval_end)
    else:
        interval_start, interval_end = find_video_intervals(user_id, video_module_id)[0:2]
    
    hist_xaxis = list(interval_start + interval_end) # merge the two lists
    hist_xaxis.append(0) # assure xaxis stems from the beginning (video_pos = 0 secs)
    hist_xaxis.append(int(video_duration)) # assure xaxis covers up to video length
    hist_xaxis = list(set(hist_xaxis)) # to remove duplicates
    hist_xaxis.sort() # abscissa values for histogram    
    midpoints = []
    for index in range(0, len(hist_xaxis)-1):
        midpoints.append((hist_xaxis[index] + hist_xaxis[index+1])/float(2))

    # ordinate values for histogram
    hist_yaxis = get_hist_height(interval_start, interval_end, midpoints)# set histogram height
    
    return hist_xaxis, hist_yaxis


# Determine video histogram height
def get_hist_height(interval_start, interval_end, points):
  
    open_intervals = 0 # number of open intervals
    close_intervals = 0 # number of close intervals
    hist_yaxis = []
    for point in points:
        for start in interval_start:
            if point >= start:
                open_intervals += 1
            else:
                break
        for end in interval_end:
            if point > end:
                close_intervals += 1                
        hist_yaxis.append(open_intervals - close_intervals)
        open_intervals = 0
        close_intervals = 0
        
    return hist_yaxis

    
# Determine how much NON-OVERLAPPED time of video a student has watched
def video_len_watched(student, video_module_id):
    # check there's an entry for this video    
    interval_start, interval_end = find_video_intervals(student, video_module_id)[0:2]
    disjointed_start = [interval_start[0]]
    disjointed_end = [interval_end[0]]
    # building non-crossed intervals
    for index in range(0,len(interval_start)-1):
        if interval_start[index+1] == disjointed_end[-1]:
            disjointed_end.pop()
            disjointed_end.append(interval_end[index+1])
            continue
        elif interval_start[index+1] > disjointed_end[-1]:
            disjointed_start.append(interval_start[index+1])
            disjointed_end.append(interval_end[index+1])
            continue
        elif interval_end[index+1] > disjointed_end[-1]:
            disjointed_end.pop()
            disjointed_end.append(interval_end[index+1])
    return [disjointed_start, disjointed_end]

    
# Given a video descriptor returns ORDERED the video intervals a student has seen
# A timestamp of the interval points is also recorded.
def find_video_intervals(student, video_module_id):
    INVOLVED_EVENTS = [
        'play_video',
        'seek_video',
    ]
    #event flags to check for duplicity
    play_flag = False # True: last event was a play_video
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
    interval_start, interval_end, vid_start_time, vid_end_time = zip(*sorted(zip(interval_start1, interval_end1, vid_start_time1, vid_end_time1)))
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
    
    
# Obtain list of events relative to videos and their relative position within the video
# For the whole class
# CT Current time
# Return format: [[CTs for play], [CTs for pause], [CTs for speed changes], [old_time list], [new_time list]]
def get_class_video_events(course, video_module_id):

    usernames_in = []
    for student in CourseEnrollment.users_enrolled_in(course.id):
        usernames_in.append(student.username.encode('utf-8'))
    class_events_times = [[],[],[],[],[]]
    for username_in in usernames_in:
        events_times = get_video_events(username_in, video_module_id)
        if events_times is not None:
            for i in range(0,len(class_events_times)):
                class_events_times[i] = class_events_times[i] + events_times[i]
                
    if class_events_times == [[],[],[],[],[]]:
        # No one in class has seen any video yet
        class_events_times = None
        
    return class_events_times


# Receives as argument [[CTs for play], [CTs for pause], [CTs for speed changes], [old_time list], [new_time list]]    
# Adapts events_times as returned from get_video_events(**kwargs) to Google Charts' scatter chart
# CT: current time
def video_events_to_scatter_chart(events_times):
    scatter_array = [['Position (s)','Play', 'Pause', 'Change speed', 'Seek from', 'Seek to']]
    i = 0
    for event_times in events_times:
        i += 1
        if len(event_times) <= 0:
            scatter_array.append([None, None, None, None, None, None])
            scatter_array[-1][i] = i
        else:
            for event_time in event_times:
                scatter_array.append([event_time, None, None, None, None, None])
                scatter_array[-1][i] = i
    
    return simplejson.dumps(scatter_array)
    
    
# Returns an array in JSON format ready to use for the arrayToDataTable method of Google Charts
def ready_for_arraytodatatable(column_headers, *columns):

    if columns[-1] is None or columns[-1] == []:
        return simplejson.dumps(None)
        
    array_to_data_table = []
    array_to_data_table.append(column_headers)
    if len(columns) > 0:
        for i in range(0, len(columns[0])):
            row = []
            for column in columns:
                row.append(column[i])
            array_to_data_table.append(row)
            
    return simplejson.dumps(array_to_data_table)
   

# Given a video event from the track_trackinglogs MySQL table returns currentTime depending on event_type
# currentTime is the position in video the event refers to
# For play_video, pause_video and speed_change_video events it refers to where video was played, paused or the speed was changed.
# For seek_video event it's actually new_time and old_time where the user moved to and from
def get_current_time(video_event):
  
    current_time = []
    
    if video_event.event_type == 'play_video' or video_event.event_type == 'pause_video':
        current_time = [eval(video_event.event)['currentTime']]
    elif video_event.event_type == 'speed_change_video':
        current_time = [eval(video_event.event)['current_time']]
    elif video_event.event_type == 'seek_video':
        current_time = [eval(video_event.event)['old_time'], eval(video_event.event)['new_time']]
    
    return current_time


# Returns daily time devoted to the activity described by the arguments
# Intervals start and end are both relative to video position
# Times start and end are both lists of Django's DateTimeField.
def get_daily_time(interval_start, interval_end, time_start, time_end):
    # Sort all list by time_start order
    [time_start, time_end, interval_start, interval_end] = zip(*sorted(zip(time_start, time_end, interval_start, interval_end)))
    interval_start = list(interval_start)
    interval_end = list(interval_end)
    time_start = list(time_start)
    time_end = list(time_end)
    
    days = [time_start[0].date()]
    daily_time = [0]
    i = 0 
    while i < len(time_start):
        if days[-1] == time_start[i].date(): # another interval to add to the same day
            if time_end[i].date() == time_start[i].date(): # the interval belongs to a single day
                daily_time[-1] += interval_end[i] - interval_start[i]
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10. 
                daily_time[-1] += 24*60*60 - time_start[i].hour*60*60 - time_start[i].minute*60 - time_start[i].second
                days.append(time_end[i].date())
                daily_time.append(time_end[i].hour*60*60 + time_end[i].minute*60 + time_end[i].second)
        else:
            days.append(time_start[i].date())
            daily_time.append(0)
            if time_end[i].date() == time_start[i].date(): # the interval belongs to a single day
                daily_time[-1] += interval_end[i] - interval_start[i]
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10.
                daily_time[-1] += 24*60*60 - time_start[i].hour*60*60 - time_start[i].minute*60 - time_start[i].second
                days.append(time_end[i].date())
                daily_time.append(time_end[i].hour*60*60 + time_end[i].minute*60 + time_end[i].second)            
        i += 1
    # Convert days from datetime.date to str in format YYYY-MM-DD
    # Currently this conversion takes place outside this function. Therefore, commented out.
    """
    days_yyyy_mm_dd = []
    for day in days:
        days_yyyy_mm_dd.append(day.isoformat())
    """
    return  [interval_start, interval_end, time_start, time_end, days, daily_time]


# Computes the time a student has dedicated to a video in seconds
#TODO Does it make sense to change the resolution to minutes?
# Returns also daily time spent on a video by the user
def daily_time_on_video(student, video_module_id):

    [interval_start, interval_end, vid_start_time, vid_end_time] = find_video_intervals(student, video_module_id)
    # We could check on either vid_start_time or vid_end_time for unwatched video
    if len(vid_start_time) > 0:
        video_days, video_daily_time = get_daily_time(interval_start, interval_end, vid_start_time, vid_end_time)[4:6]
    else:
        video_days, video_daily_time = [], 0
    
    return [video_days, video_daily_time]


# Computes the time (in seconds) a student has dedicated
# to videos (any of them) on a daily basis
#TODO Does it make sense to change the resolution to minutes?
def daily_time_on_videos(student, course_descriptor):

    accum_days = []
    accum_daily_time = []
    video_descriptors = list_video_descriptors(course_descriptor)
    for video_descriptor in video_descriptors:
        [days, daily_time] = daily_time_on_video(student, video_descriptor.location)
        if len(days) > 0:
            accum_days = accum_days + days
            accum_daily_time = accum_daily_time + daily_time
    if len(accum_days) <= 0:
        return [], 0
    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break
    
    return [days, daily_time]


# Computes the aggregated time (in seconds) all students in a course (the whole class)
# have dedicated to videos (any of them) on a daily basis
#TODO Does it make sense to change the resolution to minutes?
def class_time_on_videos(course_descriptor):

    usernames_in = []
    accum_days = []
    accum_daily_time = []
    for student in CourseEnrollment.users_enrolled_in(course_descriptor.id):
        usernames_in.append(student.username.encode('utf-8'))
    for username in usernames_in:
        [days, daily_time] = daily_time_on_videos(username, course_descriptor)
        if len(days) > 0:
            accum_days = accum_days + days
            accum_daily_time = accum_daily_time + daily_time
    if len(accum_days) <= 0:
        return [], 0

    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break        

    return [days, daily_time]


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
    return [problem_time, days, daily_time]


# Computes the time (in seconds) a student has dedicated
# to problems (any of them) on a daily basis
#TODO Does it make sense to change the resolution to minutes?
def time_on_problems(student, course_descriptor):

    accum_days = []
    accum_daily_time = []
    problem_descriptors = list_problem_descriptors(course_descriptor)[2]
    for problem_descriptor in problem_descriptors:
        days, daily_time = time_on_problem(student, problem_descriptor.location)[1:3]
        if len(days) > 0:
            accum_days = accum_days + days
            accum_daily_time = accum_daily_time + daily_time
    if len(accum_days) <= 0:
        return [], 0        
        
    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break
    
    return [days, daily_time]


# Computes the aggregated time (in seconds) all students in a course (the whole class)
# have dedicated to problems (any of them) on a daily basis
#TODO Does it make sense to change the resolution to minutes?
def class_time_on_problems(course_descriptor):

    usernames_in = []
    accum_days = []
    accum_daily_time = []
    for student in CourseEnrollment.users_enrolled_in(course_descriptor.id):
        usernames_in.append(student.username.encode('utf-8'))
    for username in usernames_in:
        [days, daily_time] = time_on_problems(username, course_descriptor)
        if len(days) > 0:
            accum_days = accum_days + days
            accum_daily_time = accum_daily_time + daily_time
    if len(accum_days) <= 0:
        return [], 0        
        
    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break        

    return [days, daily_time]


# Once we have daily time spent on video and problems, we need to put these informations together
# so that they can be jointly represented in a column chart.
# Thought for ColumnChart of Google Charts.
# Output convenient for Google Charts' arrayToDataTable()  [['day', video_time, problem_time], []]
def join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time):

    days = list(set(video_days + problem_days)) # join days and remove duplicates
    # Check whether neither video watched nor problem tried
    if len(days) <= 0:
        return simplejson.dumps(None)

    days.sort() # order the list
    # list of lists containing date, video time and problem time
    output_array = []
    for i in range(0, len(days)):
        output_array.append([days[i].isoformat(),0,0])
        try: # some video time that day
            auxiliar = video_daily_time[video_days.index(days[i])]
            output_array[i][1] = auxiliar
        except ValueError:
            pass
        try: # some problem time that day
            auxiliar = problem_daily_time[problem_days.index(days[i])]
            output_array[i][2] = auxiliar
        except ValueError:
            pass
    # Insert at the list start the column information
    output_array.insert(0, ['Day', 'Video time (s)', 'Problem time (s)'])
    return simplejson.dumps(output_array)