from django.conf.urls import patterns, url

from learning_analytics import views

urlpatterns = patterns('',
    url(r'^homework_grade$', views.homework_grade, name="homework_grade"),
    url(r'^chapter_time$', views.chapter_time, name="chapter_time"),
)
