# Function(s) invoked by Celery when scheduled to process data
# and save it to the databases for visualization info

from courseware.courses import get_course_by_id
from django.utils import simplejson
from student.models import CourseEnrollment

from models import *
from classes import *
from data_querying import *
from data_processing import *

def update_visualization_data(course_key=None):
    # course_key should be a course_key
  
    kw_consumption_module = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'module_key': '',
        'display_name': '',
        'percent_viewed': 0,
        'total_time': 0,
    }
    
    kw_video_intervals = {
        'student': '',
        'course_key': course_key,
        'module_key': '',        
        'display_name': '',
        'hist_xaxis': '',
        'hist_yaxis': '',        
    }
    
    kw_daily_consumption = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'dates': '',
        'time_per_date': '',        
    }
    
    kw_video_events = {
        'student': '',
        'course_key': course_key,
        'module_key': '',          
        'display_name': '',
        'play_events' : '',
        'pause_events' : '',
        'change_speed_events' : '',
        'seek_from_events' : '',
        'seek_to_events' : '',
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.users_enrolled_in(course_key)]
        videos_in, problems_in = videos_problems_in(course)
        video_names, video_module_keys, video_durations = get_info_videos(videos_in)
        problem_names = [x.display_name_with_default.encode('utf-8') for x in problems_in]
        problem_ids = [x.location for x in problems_in]
        
        # List of UserVideoIntervals
        users_video_intervals = []
        # List of UserTimeOnProblems
        users_time_on_problems = []
        for username_in in usernames_in:
            for video_module_key in video_module_keys:
                interval_start, interval_end, vid_start_time, vid_end_time = find_video_intervals(username_in, video_module_key)
                disjointed_start, disjointed_end = video_len_watched(interval_start, interval_end)
                users_video_intervals.append(UserVideoIntervals(username_in, video_module_key, 
                                                               interval_start, interval_end,
                                                               vid_start_time, vid_end_time,
                                                               disjointed_start, disjointed_end))
            for problem_id in problem_ids:
                problem_time, days, daily_time = time_on_problem(username_in, problem_id)
                users_time_on_problems.append(UserTimeOnProblems(username_in, problem_id, 
                                                                 problem_time, days, daily_time))          

        # ConsumptionModule table data
        accum_video_percentages = []
        accum_all_video_time = []
        accum_problem_time = []
        for username_in in usernames_in:
            kw_consumption_module['student'] = username_in
            #video modules
            kw_consumption_module['module_type'] = 'video'          
            # video_percentages (in %), all_video_time (in seconds)
            low_index = usernames_in.index(username_in)*len(video_names)
            high_index = low_index + len(video_names)
            video_percentages, all_video_time = video_consumption(users_video_intervals[low_index:high_index], video_durations)
            if video_percentages != [] and accum_video_percentages == []:
                accum_video_percentages = video_percentages
                accum_all_video_time = all_video_time
            elif video_percentages != []:
                for j in range(0, len(accum_all_video_time)):
                    accum_video_percentages[j] += video_percentages[j]
                    accum_all_video_time[j] += all_video_time[j]
            for i in range(0,len(video_percentages)):
                kw_consumption_module['module_key'] = video_module_keys[i]
                kw_consumption_module['display_name'] = video_names[i]
                kw_consumption_module['percent_viewed'] = video_percentages[i]
                kw_consumption_module['total_time'] = all_video_time[i]
                try:
                    new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                    new_entry.percent_viewed = kw_consumption_module['percent_viewed']
                    new_entry.total_time = kw_consumption_module['total_time']
                except ConsumptionModule.DoesNotExist:
                    new_entry = ConsumptionModule(**kw_consumption_module)
                new_entry.save()
            #problem modules
            kw_consumption_module['module_type'] = 'problem'
            kw_consumption_module['percent_viewed'] = None
            low_index = usernames_in.index(username_in)*len(problem_names)
            high_index = low_index + len(problem_names)   
            time_x_problem = problem_consumption(users_time_on_problems[low_index:high_index])
            if time_x_problem != [] and accum_problem_time == []:
                accum_problem_time = time_x_problem
            elif time_x_problem != []:
                for j in range(0, len(accum_all_video_time)):
                    accum_problem_time[j] += time_x_problem[j]
                for i in range(0,len(problem_names)):
                    kw_consumption_module['module_key'] = problem_ids[i]
                    kw_consumption_module['display_name'] = problem_names[i]
                    kw_consumption_module['total_time'] = time_x_problem[i]                
                    try:
                        new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                        new_entry.total_time = kw_consumption_module['total_time']
                    except ConsumptionModule.DoesNotExist:
                        new_entry = ConsumptionModule(**kw_consumption_module)                    
                    new_entry.save()
        # average values
        kw_consumption_module['student'] = '#average'
        kw_consumption_module['module_type'] = 'video'                
        for i in range(0, len(accum_video_percentages)):
            accum_video_percentages[i] = int(round(truediv(accum_video_percentages[i],len(usernames_in)),0))
            accum_all_video_time[i] = int(round(truediv(accum_all_video_time[i],len(usernames_in)),0))
            kw_consumption_module['module_key'] = video_module_keys[i]
            kw_consumption_module['display_name'] = video_names[i]
            kw_consumption_module['percent_viewed'] = accum_video_percentages[i]
            kw_consumption_module['total_time'] = accum_all_video_time[i]
            try:
                new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                new_entry.percent_viewed = kw_consumption_module['percent_viewed']
                new_entry.total_time = kw_consumption_module['total_time']
            except ConsumptionModule.DoesNotExist:
                new_entry = ConsumptionModule(**kw_consumption_module)            
            new_entry.save()
        kw_consumption_module['module_type'] = 'problem'
        kw_consumption_module['percent_viewed'] = None
        for i in range(0, len(accum_problem_time)):
            accum_problem_time[i] = truediv(accum_problem_time[i],len(usernames_in))
            kw_consumption_module['module_key'] = problem_ids[i]
            kw_consumption_module['display_name'] = problem_names[i]
            kw_consumption_module['total_time'] = accum_problem_time[i]
            try:
                new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])
                new_entry.total_time = kw_consumption_module['total_time']
            except ConsumptionModule.DoesNotExist:
                new_entry = ConsumptionModule(**kw_consumption_module)            
            new_entry.save()
 
        # VideoIntervals table data
        for video_name, video_id in zip(video_names, video_module_keys):
            accum_interval_start = []
            accum_interval_end = []
            accum_disjointed_start = []
            accum_disjointed_end = []          
            kw_video_intervals['module_key'] = video_id
            kw_video_intervals['display_name'] = video_name
            for username_in in usernames_in:
                kw_video_intervals['student'] = username_in      
                index = video_module_keys.index(video_id) + usernames_in.index(username_in)*len(video_names)
                interval_start = users_video_intervals[index].interval_start
                interval_end = users_video_intervals[index].interval_end
                accum_interval_start += interval_start
                accum_interval_end += interval_end
                accum_disjointed_start += users_video_intervals[index].disjointed_start
                accum_disjointed_end += users_video_intervals[index].disjointed_end                
                hist_xaxis, hist_yaxis = histogram_from_intervals(interval_start, interval_end, video_durations[video_module_keys.index(video_id)])
                kw_video_intervals['hist_xaxis'] = simplejson.dumps(hist_xaxis)
                kw_video_intervals['hist_yaxis'] = simplejson.dumps(hist_yaxis)
                try:
                    new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                    new_entry.hist_xaxis = kw_video_intervals['hist_xaxis']
                    new_entry.hist_yaxis = kw_video_intervals['hist_yaxis']
                except VideoIntervals.DoesNotExist:
                    new_entry = VideoIntervals(**kw_video_intervals)        
                new_entry.save()
            # Total times these video intervals have been viewed
            kw_video_intervals['student'] = '#class_total_times'
            interval_start, interval_end = sort_intervals(accum_interval_start, accum_interval_end)
            hist_xaxis, hist_yaxis = histogram_from_intervals(interval_start, interval_end, video_durations[video_module_keys.index(video_id)])
            kw_video_intervals['hist_xaxis'] = simplejson.dumps(hist_xaxis)
            kw_video_intervals['hist_yaxis'] = simplejson.dumps(hist_yaxis)
            try:
                new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                new_entry.hist_xaxis = kw_video_intervals['hist_xaxis']
                new_entry.hist_yaxis = kw_video_intervals['hist_yaxis']
            except VideoIntervals.DoesNotExist:
                new_entry = VideoIntervals(**kw_video_intervals)                    
            new_entry.save()
            
            # Total times these video intervals have been viewed
            # Every student counts a single time
            kw_video_intervals['student'] = '#one_stu_one_time'
            interval_start, interval_end = sort_intervals(accum_disjointed_start, accum_disjointed_end)
            hist_xaxis, hist_yaxis = histogram_from_intervals(interval_start, interval_end, video_durations[video_module_keys.index(video_id)])
            kw_video_intervals['hist_xaxis'] = simplejson.dumps(hist_xaxis)
            kw_video_intervals['hist_yaxis'] = simplejson.dumps(hist_yaxis)
            try:
                new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                new_entry.hist_xaxis = kw_video_intervals['hist_xaxis']
                new_entry.hist_yaxis = kw_video_intervals['hist_yaxis']
            except VideoIntervals.DoesNotExist:
                new_entry = VideoIntervals(**kw_video_intervals)                    
            new_entry.save()
            
        # DailyConsumption table data
        accum_vid_days = []
        accum_vid_daily_time = []
        accum_prob_days = []
        accum_prob_daily_time = []
        for username_in in usernames_in:
            low_index = usernames_in.index(username_in)*len(video_names)
            high_index = low_index + len(video_names)
            video_days, video_daily_time = daily_time_on_videos(users_video_intervals[low_index:high_index])
            video_days = datelist_to_isoformat(video_days)
            if len(video_days) > 0:
                accum_vid_days += video_days
                accum_vid_daily_time += video_daily_time
            low_index = usernames_in.index(username_in)*len(problem_names)
            high_index = low_index + len(problem_names)    
            problem_days, problem_daily_time = time_on_problems(users_time_on_problems[low_index:high_index])
            problem_days = datelist_to_isoformat(problem_days)
            if len(problem_days) > 0:
                accum_prob_days += problem_days
                accum_prob_daily_time += problem_daily_time
            # save to DailyConsumption table
            kw_daily_consumption['student'] = username_in
            kw_daily_consumption['module_type'] = 'video'
            kw_daily_consumption['dates'] = simplejson.dumps(video_days)
            kw_daily_consumption['time_per_date'] = simplejson.dumps(video_daily_time)
            try:
                new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
                new_entry.dates = kw_daily_consumption['dates']
                new_entry.time_per_date = kw_daily_consumption['time_per_date']
            except DailyConsumption.DoesNotExist:
                new_entry = DailyConsumption(**kw_daily_consumption)
            new_entry.save()            
            kw_daily_consumption['module_type'] = 'problem'
            kw_daily_consumption['dates'] = simplejson.dumps(problem_days)
            kw_daily_consumption['time_per_date'] = simplejson.dumps(problem_daily_time)
            try:
                new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
                new_entry.dates = kw_daily_consumption['dates']
                new_entry.time_per_date = kw_daily_consumption['time_per_date']
            except DailyConsumption.DoesNotExist:
                new_entry = DailyConsumption(**kw_daily_consumption)            
            new_entry.save()
            
        kw_daily_consumption['student'] = '#average'
        problem_days, problem_daily_time = class_time_on(accum_prob_days, accum_prob_daily_time)
        kw_daily_consumption['dates'] = simplejson.dumps(problem_days)
        kw_daily_consumption['time_per_date'] = simplejson.dumps(problem_daily_time)
        try:
            new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
            new_entry.dates = kw_daily_consumption['dates']
            new_entry.time_per_date = kw_daily_consumption['time_per_date']
        except DailyConsumption.DoesNotExist:
            new_entry = DailyConsumption(**kw_daily_consumption)        
        new_entry.save()
        kw_daily_consumption['module_type'] = 'video'
        video_days, video_daily_time = class_time_on(accum_vid_days, accum_vid_daily_time)
        kw_daily_consumption['dates'] = simplejson.dumps(video_days)
        kw_daily_consumption['time_per_date'] = simplejson.dumps(video_daily_time)
        try:
            new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
            new_entry.dates = kw_daily_consumption['dates']
            new_entry.time_per_date = kw_daily_consumption['time_per_date']
        except DailyConsumption.DoesNotExist:
            new_entry = DailyConsumption(**kw_daily_consumption)
        new_entry.save()            
            
        # VideoEvents table data
        VIDEO_EVENTS = ['play', 'pause', 'change_speed', 'seek_from', 'seek_to']
        class_events_times = [[],[],[],[],[]]
        for username_in in usernames_in:
            kw_video_events['student'] = username_in
            for video_module_key in video_module_keys:
                kw_video_events['module_key'] = video_module_key
                kw_video_events['display_name'] = video_names[video_module_keys.index(video_module_key)]
                events_times = get_video_events(username_in, video_module_key)
                if events_times is None:
                    continue
                for event in VIDEO_EVENTS:
                    kw_video_events[event + '_events'] = simplejson.dumps(events_times[VIDEO_EVENTS.index(event)])
                try:
                    new_entry = VideoEvents.objects.get(student=kw_video_events['student'], module_key=kw_video_events['module_key'])
                    new_entry.play_events = kw_video_events['play_events']
                    new_entry.pause_events = kw_video_events['pause_events']
                    new_entry.change_speed_events = kw_video_events['change_speed_events']
                    new_entry.seek_from_events = kw_video_events['seek_from_events']
                    new_entry.seek_to_events = kw_video_events['seek_to_events']                    
                except VideoEvents.DoesNotExist:
                    new_entry = VideoEvents(**kw_video_events)                
                new_entry.save()
 
    else:
        pass
      