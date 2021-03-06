from track.backends.django import TrackingLog
from learning_analytics.data import get_courses_list, get_course_students
from learning_analytics.analytics_jose import get_all_events_sql, current_schedule, minutes_between, time_schedule
from datetime import datetime
from learning_analytics.analytics import (update_DB_course_struct, update_DB_course_spent_time, update_DB_sort_course_homework, update_DB_student_grades, update_DB_course_section_accesses, update_DB_course_problem_progress, update_DB_course_video_progress)
from learning_analytics.analytics_jose import time_schedule, get_DB_time_schedule
from json import dumps
from learning_analytics.celeryHector import update_visualization_data
"""
for course in get_courses_list():
    print "%s" % (course.id)
    time_schedule(course.id)
"""


courses = get_courses_list()
for course in courses:
    #update_DB_course_struct(course.id)
    #update_DB_student_grades(course.id)
    #update_DB_course_spent_time(course.id)
    #update_DB_sort_course_homework(course.id)
    #update_DB_course_section_accesses(course.id)
    #time_schedule(course.id)
    update_visualization_data(course.id)
    #update_DB_course_problem_progress(course.id)
    #update_DB_course_video_progress(course.id)
