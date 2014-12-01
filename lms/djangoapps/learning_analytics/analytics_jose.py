from data import is_same_course
from data import get_course_students
from track.backends.django import TrackingLog
from models import TimeSchedule
import datetime

def time_schedule(course_id):
    print "time_schedule"
    students = get_course_students(course_id)
    
    morningTimeStudentCourse = 0
    afternoonTimeStudentCourse = 0
    nightTimeStudentCourse = 0
    
    for student in students:
        
        print ""
        print ""
        print ""
        print student.username
        
        firstEventOfSeries = None
        previousEvent = None     
        
        morningTimeStudent = 0
        afternoonTimeStudent = 0
        nightTimeStudent = 0
        
        currentSchedule = ""
        
        studentEvents = get_all_events_sql(course_id, student)        
        
        for currentEvent in studentEvents:
            
            print "Current schedule: %s" % currentSchedule
            
            if(currentSchedule == ""):
                currentSchedule = current_schedule(currentEvent.dtcreated.hour)
                if(previousEvent == None):                    
                    firstEventOfSeries = currentEvent
                else:
                    firstEventOfSeries = previousEvent
            else:
                print "Previous %s    Current %s" % (previousEvent.dtcreated, currentEvent.dtcreated)
                if((minutes_between(previousEvent.dtcreated,currentEvent.dtcreated) >= 30) or currentSchedule != current_schedule(currentEvent.dtcreated.hour)):                    
                    if(currentSchedule == "morning"):
                        morningTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                        print "First Event %s    Previous %s    Time: %d" % (firstEventOfSeries.dtcreated, previousEvent.dtcreated, minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated))
                        print "Morning: %d" % morningTimeStudent
                    elif(currentSchedule == "afternoon"):
                        afternoonTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                        print "First Event %s    Previous %s    Time: %d" % (firstEventOfSeries.dtcreated, previousEvent.dtcreated, minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated))
                        print "Afternoon: %d" % afternoonTimeStudent
                    elif(currentSchedule == "night"):
                        print "First Event %s    Previous %s    Time: %d" % (firstEventOfSeries.dtcreated, previousEvent.dtcreated, minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated))                        
                        print "Night: %d" % nightTimeStudent
                    currentSchedule = ""
                            
            previousEvent = currentEvent
            
        if(currentSchedule == "morning"):
            morningTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
            print "First Event %s    Previous %s    Time: %d" % (firstEventOfSeries.dtcreated, previousEvent.dtcreated, minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated))
            print "Morning: %d" % morningTimeStudent
        elif(currentSchedule == "afternoon"):
            afternoonTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
            print "First Event %s    Previous %s    Time: %d" % (firstEventOfSeries.dtcreated, previousEvent.dtcreated, minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated))
            print "Afternoon: %d" % afternoonTimeStudent
        elif(currentSchedule == "night"):
            nightTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
            print "First Event %s    Previous %s    Time: %d" % (firstEventOfSeries.dtcreated, previousEvent.dtcreated, minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated))
            print "Night: %d" % nightTimeStudent
        
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


