from track.backends.django import TrackingLog
from learning_analytics.data import get_courses_list, get_course_students
from learning_analytics.analytics_jose import get_all_events_sql, current_schedule, minutes_between, time_schedule
from datetime import datetime

for course in get_courses_list():
    print "%s" % (course.id)
    time_schedule(course.id)
