# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'CourseProbVidProgress'
        db.create_table('learning_analytics_courseprobvidprogress', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('student_id', self.gf('django.db.models.fields.IntegerField')()),
            ('course_id', self.gf('xmodule_django.models.CourseKeyField')(max_length=255, db_index=True)),
            ('progress', self.gf('django.db.models.fields.CharField')(default=u'', max_length=20000)),
            ('type', self.gf('django.db.models.fields.CharField')(default=u'PROB', max_length=32)),
            ('start_time', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True)),
            ('end_time', self.gf('django.db.models.fields.DateTimeField')(default=None, null=True)),
            ('delta', self.gf('django.db.models.fields.FloatField')()),
            ('last_calc', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('learning_analytics', ['CourseProbVidProgress'])

        # Adding unique constraint on 'CourseProbVidProgress', fields ['student_id', 'course_id', 'type']
        db.create_unique('learning_analytics_courseprobvidprogress', ['student_id', 'course_id', 'type'])


        # Changing field 'CourseAccesses.accesses'
        db.alter_column('learning_analytics_courseaccesses', 'accesses', self.gf('django.db.models.fields.CharField')(max_length=10000))

        # Changing field 'CourseTime.time_spent'
        db.alter_column('learning_analytics_coursetime', 'time_spent', self.gf('django.db.models.fields.CharField')(max_length=10000))

    def backwards(self, orm):
        # Removing unique constraint on 'CourseProbVidProgress', fields ['student_id', 'course_id', 'type']
        db.delete_unique('learning_analytics_courseprobvidprogress', ['student_id', 'course_id', 'type'])

        # Deleting model 'CourseProbVidProgress'
        db.delete_table('learning_analytics_courseprobvidprogress')


        # Changing field 'CourseAccesses.accesses'
        db.alter_column('learning_analytics_courseaccesses', 'accesses', self.gf('django.db.models.fields.CharField')(max_length=2000))

        # Changing field 'CourseTime.time_spent'
        db.alter_column('learning_analytics_coursetime', 'time_spent', self.gf('django.db.models.fields.CharField')(max_length=1000))

    models = {
        'learning_analytics.consumptionmodule': {
            'Meta': {'unique_together': "((u'student', u'module_key'),)", 'object_name': 'ConsumptionModule'},
            'course_key': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module_key': ('xmodule_django.models.LocationKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'module_type': ('django.db.models.fields.CharField', [], {'default': "u'video'", 'max_length': '32', 'db_index': 'True'}),
            'percent_viewed': ('django.db.models.fields.FloatField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'student': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'total_time': ('django.db.models.fields.FloatField', [], {'db_index': 'True'})
        },
        'learning_analytics.courseaccesses': {
            'Meta': {'unique_together': "((u'student_id', u'course_id'),)", 'object_name': 'CourseAccesses'},
            'accesses': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10000'}),
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_calc': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'student_id': ('django.db.models.fields.IntegerField', [], {})
        },
        'learning_analytics.courseprobvidprogress': {
            'Meta': {'unique_together': "((u'student_id', u'course_id', u'type'),)", 'object_name': 'CourseProbVidProgress'},
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'delta': ('django.db.models.fields.FloatField', [], {}),
            'end_time': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_calc': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'progress': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20000'}),
            'start_time': ('django.db.models.fields.DateTimeField', [], {'default': 'None', 'null': 'True'}),
            'student_id': ('django.db.models.fields.IntegerField', [], {}),
            'type': ('django.db.models.fields.CharField', [], {'default': "u'PROB'", 'max_length': '32'})
        },
        'learning_analytics.coursestruct': {
            'Meta': {'unique_together': "((u'module_state_key', u'course_id'),)", 'object_name': 'CourseStruct'},
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'father': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['learning_analytics.CourseStruct']", 'null': 'True', 'blank': 'True'}),
            'graded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.IntegerField', [], {}),
            'module_state_key': ('xmodule_django.models.LocationKeyField', [], {'max_length': '255', 'db_column': "u'module_id'"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'released': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'section_type': ('django.db.models.fields.CharField', [], {'default': "u'chapter'", 'max_length': '32', 'db_index': 'True'})
        },
        'learning_analytics.coursetime': {
            'Meta': {'unique_together': "((u'student_id', u'course_id'),)", 'object_name': 'CourseTime'},
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_calc': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'student_id': ('django.db.models.fields.IntegerField', [], {}),
            'time_spent': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10000'})
        },
        'learning_analytics.dailyconsumption': {
            'Meta': {'unique_together': "((u'student', u'course_key', u'module_type'),)", 'object_name': 'DailyConsumption'},
            'course_key': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'dates': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module_type': ('django.db.models.fields.CharField', [], {'default': "u'video'", 'max_length': '32', 'db_index': 'True'}),
            'student': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'time_per_date': ('django.db.models.fields.TextField', [], {})
        },
        'learning_analytics.sortgrades': {
            'Meta': {'unique_together': "((u'label', u'course_id', u'sort_type'),)", 'object_name': 'SortGrades'},
            'category': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'last_calc': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            'num_fail': ('django.db.models.fields.IntegerField', [], {}),
            'num_not': ('django.db.models.fields.IntegerField', [], {}),
            'num_pass': ('django.db.models.fields.IntegerField', [], {}),
            'num_prof': ('django.db.models.fields.IntegerField', [], {}),
            'sort_type': ('django.db.models.fields.CharField', [], {'default': "u'GS'", 'max_length': '32'})
        },
        'learning_analytics.studentgrades': {
            'Meta': {'unique_together': "((u'student_id', u'course_id'),)", 'object_name': 'StudentGrades'},
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'grade_group': ('django.db.models.fields.CharField', [], {'default': "u'FAIL'", 'max_length': '32'}),
            'grades': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_calc': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'student_id': ('django.db.models.fields.IntegerField', [], {})
        },
        'learning_analytics.timeschedule': {
            'Meta': {'unique_together': "((u'student_id', u'course_id'),)", 'object_name': 'TimeSchedule'},
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_calc': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'student_id': ('django.db.models.fields.IntegerField', [], {}),
            'time_schedule': ('django.db.models.fields.TextField', [], {'default': "u''"})
        },
        'learning_analytics.videoevents': {
            'Meta': {'unique_together': "((u'student', u'module_key'),)", 'object_name': 'VideoEvents'},
            'change_speed_events': ('django.db.models.fields.TextField', [], {}),
            'course_key': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module_key': ('xmodule_django.models.LocationKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'pause_events': ('django.db.models.fields.TextField', [], {}),
            'play_events': ('django.db.models.fields.TextField', [], {}),
            'seek_from_events': ('django.db.models.fields.TextField', [], {}),
            'seek_to_events': ('django.db.models.fields.TextField', [], {}),
            'student': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'})
        },
        'learning_analytics.videointervals': {
            'Meta': {'unique_together': "((u'student', u'module_key'),)", 'object_name': 'VideoIntervals'},
            'course_key': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'hist_xaxis': ('django.db.models.fields.TextField', [], {}),
            'hist_yaxis': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module_key': ('xmodule_django.models.LocationKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'student': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'})
        }
    }

    complete_apps = ['learning_analytics']