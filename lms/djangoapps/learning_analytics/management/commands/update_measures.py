#!/usr/bin/python

from track.backends.django import TrackingLog

from datetime import datetime

from learning_analytics.data import get_courses_list, get_course_students, get_course_module, get_course_key
from learning_analytics.analytics import (update_DB_course_struct, update_DB_course_spent_time, update_DB_sort_course_homework, update_DB_student_grades, update_DB_course_section_accesses, update_DB_course_problem_progress, update_DB_course_video_progress, update_visualization_data, time_schedule)

from django.core.management.base import BaseCommand


class Command(BaseCommand):


    def handle(self, *args, **options):
    
        course_id = get_course_key("UC3M/EVAL2014/DECEMBER")
        #course_id = get_course_key("UC3M/Q103/2014")
        
        update_DB_course_struct(course_id)
        update_DB_student_grades(course_id)
        update_DB_course_spent_time(course_id)
        update_DB_sort_course_homework(course_id)
        update_DB_course_section_accesses(course_id)
        time_schedule(course_id)
        update_visualization_data(course_id)
        update_DB_course_problem_progress(course_id)
        update_DB_course_video_progress(course_id)
