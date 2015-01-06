from __future__ import unicode_literals
from django.db import models

from xmodule_django.models import CourseKeyField, LocationKeyField

# Create your models here.
class CourseStruct(models.Model):
    SECTION_TYPES = (('chapter', 'chapter'),
                     ('sequential', 'sequential'),
                     ('vertical', 'vertical'),)
    # Section description
    course_id = CourseKeyField(max_length=255, db_index=True)
    module_state_key = LocationKeyField(max_length=255, db_column='module_id')
    name = models.CharField(max_length=255)
    section_type = models.CharField(max_length=32, choices=SECTION_TYPES, default='chapter' , db_index=True)
    index = models.IntegerField()
    father = models.ForeignKey('self', limit_choices_to={'section_type': 'chapter'}, blank=True, null=True)
    # Data
    graded = models.BooleanField(default=False)
    released = models.BooleanField(default=False)
    
    class Meta:
        unique_together = (('module_state_key', 'course_id'),)
    
    # Set fahter to null if section_type is chapter
    def __init__(self, *args, **kwargs):
        super(CourseStruct, self).__init__(*args, **kwargs)
        self.section_type = self.module_state_key.category    


class SortGrades(models.Model):
    SORT_TYPES = (('GS', 'GRADED_SECTIONS'),
                  ('WS', 'WEIGHT_SECTIONS'),)
    # Section description
    course_id = CourseKeyField(max_length=255, db_index=True)
    sort_type = models.CharField(max_length=32, choices=SORT_TYPES, default='GS')
    category = models.CharField(max_length=255, default='')
    label = models.CharField(max_length=255, default='')
    name = models.CharField(max_length=255, default='')
    
    # Sort grades
    num_not = models.IntegerField()
    num_fail = models.IntegerField()
    num_pass = models.IntegerField()
    num_prof = models.IntegerField()
    
    # Date
    last_calc = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = (('label', 'course_id', 'sort_type'),)

class CourseTime(models.Model):
    # Constants for student_id
    ALL_STUDENTS = -1
    PROF_GROUP = -2
    PASS_GROUP = -3
    FAIL_GROUP = -4
    
    # Data
    student_id = models.IntegerField()
    course_id = CourseKeyField(max_length=255, db_index=True)
    time_spent = models.CharField(max_length=10000, default='')
    
    # Date
    last_calc = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = (('student_id', 'course_id'),) 
        

class CourseAccesses(models.Model):
    # Constants for student_id
    ALL_STUDENTS = -1
    PROF_GROUP = -2
    PASS_GROUP = -3
    FAIL_GROUP = -4
    
    # Data
    student_id = models.IntegerField()
    course_id = CourseKeyField(max_length=255, db_index=True)
    accesses = models.CharField(max_length=10000, default='')
    
    # Date
    last_calc = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = (('student_id', 'course_id'),)
 
             
class StudentGrades(models.Model):
    ALL_STUDENTS = -1
    PROF_GROUP = -2
    PASS_GROUP = -3
    FAIL_GROUP = -4
    
    GRADE_TYPES = (('PROF', 'Proficiency'),
                   ('OK', 'Pass'),
                   ('FAIL', 'Fail'))
    
    # Data
    student_id = models.IntegerField()
    course_id = CourseKeyField(max_length=255, db_index=True)
    grades = models.TextField(default='')
    grade_group = models.CharField(max_length=32, choices=GRADE_TYPES, default='FAIL')
    
    # Date
    last_calc = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = (('student_id', 'course_id'),)


class CourseProbVidProgress(models.Model):
    # Constants for student_id
    ALL_STUDENTS = -1
    PROF_GROUP = -2
    PASS_GROUP = -3
    FAIL_GROUP = -4
    
    # Progress type
    PROGRESS_TYPE = (('PROB', 'problem'),
                     ('VID', 'video'))
    
    # Data
    student_id = models.IntegerField()
    course_id = CourseKeyField(max_length=255, db_index=True)
    progress = models.CharField(max_length=20000, default='')
    type = models.CharField(max_length=32, choices=PROGRESS_TYPE, default='PROB')
    start_time = models.DateTimeField(auto_now=False, null=True, default=None)
    end_time = models.DateTimeField(auto_now=False, null=True, default=None)
    delta = models.FloatField()
    # Date
    last_calc = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = (('student_id', 'course_id', 'type'),)
        
        
class TimeSchedule(models.Model):
    # Constants for student_id
    ALL_STUDENTS = -1
    PROF_GROUP = -2
    PASS_GROUP = -3
    FAIL_GROUP = -4
    
    # Data
    student_id = models.IntegerField()
    course_id = CourseKeyField(max_length=255, db_index=True)
    time_schedule = models.TextField(default='')
    
    # Date
    last_calc = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = (('student_id', 'course_id'),)
        
        
# Model for data to be used on 'Video time watched', 'Video time distribution'
# and 'Problem time distribution' charts. Related to time spent on modules, 
# specifically at this time video and problem ones.
class ConsumptionModule(models.Model):

    # This model for student is invalid as it does not allow for average and aggregate values.
    #student = models.ForeignKey(User, db_index=True)
    
    student = models.CharField(max_length=32, db_index=True)
    #course_key
    course_key = CourseKeyField(max_length=255, db_index=True)
    #OLD course_key = models.CharField(max_length=255, db_index=True)

    MODULE_TYPES = (('problem', 'problem'),
                    ('video', 'video'),
                    )

    module_type = models.CharField(max_length=32, choices=MODULE_TYPES, default='video', db_index=True)
    module_key = LocationKeyField(max_length=255, db_index=True)
    # Module's display name
    display_name = models.CharField(max_length=255, db_index=True)
    
    total_time = models.FloatField(db_index=True)
    
    # For videos only. Time of non-overlapped video viewed in seconds
    percent_viewed = models.FloatField(null=True, blank=True, db_index=True)    
    
    class Meta:
        unique_together = (('student', 'module_key'),)    

    def __repr__(self):
        return 'ConsumptionModule<%r>' % ({
            'student': self.student,
            'course_key': self.course_key,
            'module_type': self.module_type,
            'module_key': self.module_key,
            'display_name': self.display_name,
            'total_time': self.total_time,
            'percent_viewed': self.percent_viewed,
        },)        
        
    def __unicode__(self):
        return unicode(repr(self))    
    

# Model for data to be used on 'Daily time on video and problems' chart.
# Related to daily time spent on modules, specifically at this time
# video and problem ones. 
class DailyConsumption(models.Model):

    student = models.CharField(max_length=32, db_index=True)    
    #course_key
    course_key = CourseKeyField(max_length=255, db_index=True)
    #OLD course_key = models.CharField(max_length=255, db_index=True)

    MODULE_TYPES = (('problem', 'problem'),
                    ('video', 'video'),
                    )

    module_type = models.CharField(max_length=32, choices=MODULE_TYPES, default='video', db_index=True)
    
    # DateField fields use a Python datetime object to store data.
    # Databases do not store datetime objects, so the field value
    # must be converted into an ISO-compliant date string for insertion into the database.
    # Therefore a string representation of date is used.
    #date = models.DateField(db_index=True)
    
    dates = models.TextField(db_index=False)
    time_per_date = models.TextField(db_index=False)
    
    class Meta:
        unique_together = (('student', 'course_key', 'module_type'),)

    def __repr__(self):
        return 'DailyConsumption<%r>' % ({
            'student': self.student,
            'course_key': self.course_key,
            'module_type': self.module_type,
            'dates': self.dates,
            'time_per_date': self.time_per_date,
        },)
        
    def __unicode__(self):
        return unicode(repr(self))
        

# Model for data to be used on 'Video intervals repetition' chart.
# Related to how many times a student has watched a particular interval.     
class VideoIntervals(models.Model):
  
    student = models.CharField(max_length=32, db_index=True)    
    #course_key
    course_key = CourseKeyField(max_length=255, db_index=True)
    #OLD course_key = models.CharField(max_length=255, db_index=True)
    module_key = LocationKeyField(max_length=255, db_index=True)
    
    # Module's display name
    display_name = models.CharField(max_length=255, db_index=True)
    
    hist_xaxis = models.TextField(db_index=False)
    hist_yaxis = models.TextField(db_index=False)

    class Meta:
        unique_together = (('student', 'module_key'),)

    def __repr__(self):
        return 'VideoIntervals<%r>' % ({
            'student': self.student,
            'course_key': self.course_key,
            'module_key': self.module_key,
            'display_name': self.display_name,
            'hist_xaxis': self.hist_xaxis,
            'hist_yaxis': self.hist_yaxis,            
        },)
    
    def __unicode__(self):
        return unicode(repr(self))    


# Model for data to be used on 'Video events distribution within video length' chart.
# Related to the position of user interaction with videos
class VideoEvents(models.Model):

    student = models.CharField(max_length=32, db_index=True) 
    # Here the model field using ForeignKey makes sense since for this model '#average' student is not used
    # However, for similarity to the other models here, CharField has been used.
    #student = models.ForeignKey(User, db_index=True)
    #course_key
    course_key = CourseKeyField(max_length=255, db_index=True)
    #OLD course_key = models.CharField(max_length=255, db_index=True)
    module_key = LocationKeyField(max_length=255, db_index=True)
    
    # Module's display name
    display_name = models.CharField(max_length=255, db_index=True)
    
    play_events = models.TextField(db_index=False)
    pause_events = models.TextField(db_index=False)
    change_speed_events = models.TextField(db_index=False)
    seek_from_events = models.TextField(db_index=False)
    seek_to_events = models.TextField(db_index=False)

    class Meta:
        unique_together = (('student', 'module_key'),)

    def __repr__(self):
        return 'VideoEvents<%r>' % ({
            'student': self.student,
            'course_key': self.course_key,
            'module_key': self.module_key,
            'display_name': self.display_name,
            'play_events': self.play_events,
            'pause_events': self.pause_events,  
            'change_speed_events': self.change_speed_events,
            'seek_from_events': self.seek_from_events, 
            'seek_to_events': self.seek_to_events,
        },)
            
    def __unicode__(self):
        return unicode(repr(self))
