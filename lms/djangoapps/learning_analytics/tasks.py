from celery import task
import logging

from analytics import update_DB_course_struct, update_DB_course_spent_time, update_DB_sort_course_homework, update_DB_student_grades, update_DB_course_section_accesses, update_DB_course_problem_progress, update_DB_course_video_progress, time_schedule, update_visualization_data

from data import get_courses_list, get_course_key
from opaque_keys.edx.locations import SlashSeparatedCourseKey


@task()
def update_DB_analytics():
	"""
	Update learning analytics DB data
	courses = get_courses_list()
		for course in courses:
	"""
	logging.info("Starting update_DB_analytics()")
	course_id = get_course_key("CEPA_Sierra_Norte/C1/2015")
		
	update_DB_course_struct(course_id) #OK
	update_DB_student_grades(course_id) # OK
	update_DB_course_spent_time(course_id) #OK
	update_DB_sort_course_homework(course_id) #OK
	update_DB_course_section_accesses(course_id) #OK
	time_schedule(course_id) #OK
	update_visualization_data(course_id) #OK
	update_DB_course_problem_progress(course_id) #OK
	update_DB_course_video_progress(course_id) #OK
	
	logging.info("update_DB_analytics() is finished")
	"""
	courses = get_courses_list()
		for course in courses:
	"""