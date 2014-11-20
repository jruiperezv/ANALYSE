from celery import task

from analytics import update_DB_course_spent_time, update_DB_sort_course_homework, update_DB_student_grades, update_DB_course_section_accesses
from data import get_courses_list
from opaque_keys.edx.locations import SlashSeparatedCourseKey


@task()
def update_DB_analytics():
	"""
	Update learning analytics DB data
	"""
	courses = get_courses_list()
	for course in courses:
		update_DB_student_grades(course.id)
		update_DB_course_spent_time(course.id)
		update_DB_sort_course_homework(course.id)
		update_DB_course_section_accesses(course.id)