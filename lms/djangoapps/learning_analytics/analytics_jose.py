from data import is_same_course
from data import get_course_students
from track.backends.django import TrackingLog
from models import TimeSchedule
import datetime
import ast

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
    
def minutes_between(d1, d2):
    
    elapsed_time = d2 - d1
    return (elapsed_time.days * 86400 + elapsed_time.seconds)/60
    
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

def get_all_events_sql(course_key, student):
    events = TrackingLog.objects.filter(username=student).order_by('time')
    # Filter events with course_key
    filter_id = []
    for event in events:
        # Filter browser events with course_key
        if (event.event_source == 'browser'):
            if (is_same_course(event.page, course_key)):
                filter_id.append(event.id)
                
        # Filter server events with course_id
        elif event.event_source == 'server':
            split_url = filter(None, event.event_type.split('/'))
            if len(split_url) != 0: 
                if split_url[0] == 'courses':
                    if (is_same_course(event.event_type, course_key)):
                        filter_id.append(event.id)
                                
    return events.filter(id__in=filter_id)

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


