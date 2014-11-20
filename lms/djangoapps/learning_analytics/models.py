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
        unique_together = (('label', 'course_id'),)

class CourseTime(models.Model):
    # Constants for student_id
    ALL_STUDENTS = -1
    PROF_GROUP = -2
    PASS_GROUP = -3
    FAIL_GROUP = -4
    
    # Data
    student_id = models.IntegerField()
    course_id = CourseKeyField(max_length=255, db_index=True)
    time_spent = models.CharField(max_length=1000, default='')
    
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
    accesses = models.CharField(max_length=2000, default='')
    
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
