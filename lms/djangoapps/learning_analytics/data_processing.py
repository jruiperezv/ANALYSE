# Functions that process data for learning analytics

from django.utils import simplejson
import gdata.youtube
import gdata.youtube.service
from operator import truediv
import re

##########################################################################
######################## VIDEO-ONLY FUNCTIONS ############################
##########################################################################
 
 
# Returns info of videos in course.
# Specifically returns their names, durations and module_ids
def get_info_videos(video_descriptors):
  
    video_names = []
    youtube_ids = []
    video_durations = []
    video_module_ids = []
    
    for video_descriptor in video_descriptors:
        video_names.append(video_descriptor.display_name_with_default.encode('utf-8'))
        youtube_ids.append(video_descriptor.__dict__['_field_data_cache']['youtube_id_1_0'].encode('utf-8'))
        video_module_ids.append(video_descriptor.location)
        
    for youtube_id in youtube_ids:
        video_durations.append(float(id_to_length(youtube_id))) #float useful for video_percentages to avoid precision loss
        
    return video_names, video_module_ids, video_durations
     
    
# Returns video consumption non-overlapped (%) and total (in seconds)
# for a certain student relative and absolute time watched for every 
# video in video_module_ids
def video_consumption(user_video_intervals, video_durations):

    # Non-overlapped video time
    stu_video_seen = []
    # Total video time seen
    all_video_time = []    
    for video in user_video_intervals:
        interval_sum = 0
        aux_start = video.disjointed_start
        aux_end = video.disjointed_end
        video_time = 0
        interval_start = video.interval_start
        interval_end = video.interval_end
        for start, end, int_start, int_end in zip(aux_start,aux_end, interval_start, interval_end):
            interval_sum += end - start
            video_time += int_end - int_start
        stu_video_seen.append(interval_sum)
        all_video_time.append(video_time)        
        
    if sum(stu_video_seen) <= 0:
        return [], []
        
    video_percentages = map(truediv, stu_video_seen, video_durations)
    video_percentages = [val*100 for val in video_percentages]
    video_percentages = [int(round(val,0)) for val in video_percentages]
    # Artificially ensures  percentages do not surpass 100%, which
    # could happen slightly from the 1s adjustment in id_to_length function
    for i in range(0,len(video_percentages)):
        if video_percentages[i] > 100:
            video_percentages[i] = 100
  
    return video_percentages, all_video_time

    
# Determines NON-OVERLAPPED intervals from a set of intervals
def video_len_watched(interval_start, interval_end):

    disjointed_start = [interval_start[0]]
    disjointed_end = [interval_end[0]]
    # building non-crossed intervals
    for index in range(0,len(interval_start)-1):
        if interval_start[index+1] == disjointed_end[-1]:
            disjointed_end.pop()
            disjointed_end.append(interval_end[index+1])
            continue
        elif interval_start[index+1] > disjointed_end[-1]:
            disjointed_start.append(interval_start[index+1])
            disjointed_end.append(interval_end[index+1])
            continue
        elif interval_end[index+1] > disjointed_end[-1]:
            disjointed_end.pop()
            disjointed_end.append(interval_end[index+1])
    return disjointed_start, disjointed_end


# Determines the histogram information for a certain video given the 
# intervals a certain user has viewed and the video_duration itself
def histogram_from_intervals(interval_start, interval_end, video_duration):
  
    hist_xaxis = list(interval_start + interval_end) # merge the two lists
    hist_xaxis.append(0) # assure xaxis stems from the beginning (video_pos = 0 secs)
    hist_xaxis.append(int(video_duration)) # assure xaxis covers up to video length
    hist_xaxis = list(set(hist_xaxis)) # to remove duplicates
    hist_xaxis.sort() # abscissa values for histogram    
    midpoints = []
    for index in range(0, len(hist_xaxis)-1):
        midpoints.append((hist_xaxis[index] + hist_xaxis[index+1])/float(2))

    # ordinate values for histogram
    hist_yaxis = get_hist_height(interval_start, interval_end, midpoints)# set histogram height
    
    return hist_xaxis, hist_yaxis


# Determine video histogram height
def get_hist_height(interval_start, interval_end, points):
  
    open_intervals = 0 # number of open intervals
    close_intervals = 0 # number of close intervals
    hist_yaxis = []
    for point in points:
        for start in interval_start:
            if point >= start:
                open_intervals += 1
            else:
                break
        for end in interval_end:
            if point > end:
                close_intervals += 1                
        hist_yaxis.append(open_intervals - close_intervals)
        open_intervals = 0
        close_intervals = 0
        
    return hist_yaxis

    
# Returns an ordered list of intervals for start and ending points        
def sort_intervals(interval_start, interval_end):
  
    interval_start, interval_end = zip(*sorted(zip(interval_start, interval_end)))
    interval_start = list(interval_start)
    interval_end = list(interval_end)
    
    return interval_start, interval_end

    
# Returns daily time devoted to the activity described by the arguments
# Intervals start and end are both relative to video position
# Times start and end are both lists of Django's DateTimeField.
def get_daily_time(interval_start, interval_end, time_start, time_end):
    # Sort all list by time_start order
    [time_start, time_end, interval_start, interval_end] = zip(*sorted(zip(time_start, time_end, interval_start, interval_end)))
    interval_start = list(interval_start)
    interval_end = list(interval_end)
    time_start = list(time_start)
    time_end = list(time_end)
    
    days = [time_start[0].date()]
    daily_time = [0]
    i = 0 
    while i < len(time_start):
        if days[-1] == time_start[i].date(): # another interval to add to the same day
            if time_end[i].date() == time_start[i].date(): # the interval belongs to a single day
                daily_time[-1] += interval_end[i] - interval_start[i]
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10. 
                daily_time[-1] += 24*60*60 - time_start[i].hour*60*60 - time_start[i].minute*60 - time_start[i].second
                days.append(time_end[i].date())
                daily_time.append(time_end[i].hour*60*60 + time_end[i].minute*60 + time_end[i].second)
        else:
            days.append(time_start[i].date())
            daily_time.append(0)
            if time_end[i].date() == time_start[i].date(): # the interval belongs to a single day
                daily_time[-1] += interval_end[i] - interval_start[i]
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10.
                daily_time[-1] += 24*60*60 - time_start[i].hour*60*60 - time_start[i].minute*60 - time_start[i].second
                days.append(time_end[i].date())
                daily_time.append(time_end[i].hour*60*60 + time_end[i].minute*60 + time_end[i].second)            
        i += 1
    # Convert days from datetime.date to str in format YYYY-MM-DD
    # Currently this conversion takes place outside this function. Therefore, commented out.
    """
    days_yyyy_mm_dd = []
    for day in days:
        days_yyyy_mm_dd.append(day.isoformat())
    """
    return  days, daily_time


#TODO Does it make sense to change the resolution to minutes?
# Returns daily time spent on a video for a the user
def daily_time_on_video(interval_start, interval_end, vid_start_time, vid_end_time):

    # We could check on either vid_start_time or vid_end_time for unwatched video
    if len(vid_start_time) > 0:
        video_days, video_daily_time = get_daily_time(interval_start, interval_end, vid_start_time, vid_end_time)
    else:
        video_days, video_daily_time = [], 0
    
    return video_days, video_daily_time

    
# Computes the time (in seconds) a student has dedicated
# to videos (any of them) on a daily basis
#TODO Does it make sense to change the resolution to minutes?
# Receives as argument a list of UserVideoIntervals
def daily_time_on_videos(user_video_intervals):

    accum_days = []
    accum_daily_time = []
    for video in user_video_intervals:
        interval_start = video.interval_start
        interval_end = video.interval_end
        vid_start_time = video.vid_start_time
        vid_end_time = video.vid_end_time
        days, daily_time = daily_time_on_video(interval_start, interval_end, vid_start_time, vid_end_time)
        if len(days) > 0:
            accum_days = accum_days + days
            accum_daily_time = accum_daily_time + daily_time
    if len(accum_days) <= 0:
        return [], 0
    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break
    
    return days, daily_time
   

# Given a video event from the track_trackinglogs MySQL table returns currentTime depending on event_type
# currentTime is the position in video the event refers to
# For play_video, pause_video and speed_change_video events it refers to where video was played, paused or the speed was changed.
# For seek_video event it's actually new_time and old_time where the user moved to and from
def get_current_time(video_event):
  
    current_time = []
    
    if video_event.event_type == 'play_video' or video_event.event_type == 'pause_video':
        current_time = [eval(video_event.event)['currentTime']]
    elif video_event.event_type == 'speed_change_video':
        current_time = [eval(video_event.event)['current_time']]
    elif video_event.event_type == 'seek_video':
        current_time = [eval(video_event.event)['old_time'], eval(video_event.event)['new_time']]
    
    return current_time


# Receives as argument [[CTs for play], [CTs for pause], [CTs for speed changes], [old_time list], [new_time list]]    
# Adapts events_times as returned from get_video_events(**kwargs) to Google Charts' scatter chart
# CT: current time
def video_events_to_scatter_chart(events_times):
    scatter_array = [['Position (s)','Play', 'Pause', 'Change speed', 'Seek from', 'Seek to']]
    i = 0
    for event_times in events_times:
        i += 1
        if len(event_times) <= 0:
            scatter_array.append([None, None, None, None, None, None])
            scatter_array[-1][i] = i
        else:
            for event_time in event_times:
                scatter_array.append([event_time, None, None, None, None, None])
                scatter_array[-1][i] = i
    
    return simplejson.dumps(scatter_array)


# Convert a time in format HH:MM:SS to seconds
def hhmmss_to_secs(hhmmss):
    if re.match('[0-9]{2}(:[0-5][0-9]){2}', hhmmss) is None:
        return 0
    else:
        split = hhmmss.split(':')
        hours = int(split[0])
        minutes = int(split[1])
        seconds = int(split[2])
        return hours*60*60+minutes*60+seconds


# Retrieve video-length via Youtube given its ID
def id_to_length(youtube_id):
  
    yt_service = gdata.youtube.service.YouTubeService()

    # Turn on HTTPS/SSL access.
    # Note: SSL is not available at this time for uploads.
    yt_service.ssl = True

    entry = yt_service.GetYouTubeVideoEntry(video_id=youtube_id)

    # Maximum video position registered in the platform differs around 1s
    # wrt youtube duration. Thus 1 is subtracted to compensate.
    return eval(entry.media.duration.seconds) - 1

        
# DEPRECATED in Celery-oriented architecture version
# Returns info to represent a histogram with video intervals watched 
"""   
def video_histogram_info(user_id, video_module_id, video_duration, course):

    CLASS_AGGREGATES = ['#class_total_times', '#one_stu_one_time']
    if user_id in CLASS_AGGREGATES:
        interval_start = []
        interval_end = []
        for username_in in usernames_in:
            if user_id == '#class_total_times':
                startings, endings = find_video_intervals(username_in, video_module_id)[0:2]
            elif user_id == '#one_stu_one_time':
                startings, endings = video_len_watched(username_in, video_module_id)
            interval_start = interval_start + startings
            interval_end = interval_end + endings
        # sorting intervals
        interval_start, interval_end = zip(*sorted(zip(interval_start, interval_end)))
        interval_start = list(interval_start)
        interval_end = list(interval_end)
    else:
        interval_start, interval_end = find_video_intervals(user_id, video_module_id)[0:2]
    
    hist_xaxis = list(interval_start + interval_end) # merge the two lists
    hist_xaxis.append(0) # assure xaxis stems from the beginning (video_pos = 0 secs)
    hist_xaxis.append(int(video_duration)) # assure xaxis covers up to video length
    hist_xaxis = list(set(hist_xaxis)) # to remove duplicates
    hist_xaxis.sort() # abscissa values for histogram    
    midpoints = []
    for index in range(0, len(hist_xaxis)-1):
        midpoints.append((hist_xaxis[index] + hist_xaxis[index+1])/float(2))

    # ordinate values for histogram
    hist_yaxis = get_hist_height(interval_start, interval_end, midpoints)# set histogram height
    
    return hist_xaxis, hist_yaxis
"""
    
##########################################################################
######################## PROBLEM-ONLY FUNCTIONS ##########################
##########################################################################    


# Returns time spent on every problem in problem_ids for a certain student
def problem_consumption(user_time_on_problems):
  
    time_x_problem = []
    for problem in user_time_on_problems:
        time_x_problem.append(problem.problem_time)
    if sum(time_x_problem) <= 0:
        time_x_problem = []
    
    return time_x_problem

    
# Computes the time (in seconds) a student has dedicated
# to problems (any of them) on a daily basis
#TODO Does it make sense to change the resolution to minutes?
def time_on_problems(user_time_on_problems):

    accum_days = []
    accum_daily_time = []
    for user_time_on_problem in user_time_on_problems:
        days = user_time_on_problem.days
        daily_time = user_time_on_problem.daily_time
        if len(days) > 0:
            accum_days = accum_days + days
            accum_daily_time = accum_daily_time + daily_time
    if len(accum_days) <= 0:
        return [], 0        
        
    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break
    
    return days, daily_time

    
##########################################################################
######################## MIXED-MODULES FUNCTIONS #########################
##########################################################################


# Return two lists for video and problem descriptors respectively in the course
def videos_problems_in(course_descriptor):

    MODULES_TO_FIND = [u'video', u'problem']
    # Lists for video and problem descriptors
    videos_in = []
    problems_in = []
    video_problem_list = [videos_in, problems_in]
    
    for chapter in course_descriptor.get_children():
        if chapter.location.category in MODULES_TO_FIND:
            video_problem_list[MODULES_TO_FIND.index(chapter.location.category)].append(chapter)
        else:
            for sequential_or_videosequence in chapter.get_children():
                if sequential_or_videosequence.location.category in MODULES_TO_FIND:
                    video_problem_list[MODULES_TO_FIND.index(sequential_or_videosequence.location.category)].append(sequential_or_videosequence)
                else:
                    for vertical_or_problemset in sequential_or_videosequence.get_children():
                        if vertical_or_problemset.location.category in MODULES_TO_FIND:
                            video_problem_list[MODULES_TO_FIND.index(vertical_or_problemset.location.category)].append(vertical_or_problemset)
                        else:
                            for content in vertical_or_problemset.get_children():
                                if content.location.category in MODULES_TO_FIND:
                                    video_problem_list[MODULES_TO_FIND.index(content.location.category)].append(content)                              

    return video_problem_list

    
# Computes the aggregated time (in seconds) all students in a course (the whole class)
# have dedicated to a module type on a daily basis
#TODO Does it make sense to change the resolution to minutes?
def class_time_on(accum_days, accum_daily_time):

    if len(accum_days) <= 0:
        return [], 0

    days = list(set(accum_days)) # to remove duplicates
    days.sort()
    daily_time = []
    for i in range(0,len(days)):
        daily_time.append(0)
        while True:
            try:
                daily_time[i] += accum_daily_time[accum_days.index(days[i])]
                accum_daily_time.pop(accum_days.index(days[i]))
                accum_days.remove(days[i])
            except ValueError:
                break        

    return days, daily_time
    
    
# Returns an array in JSON format ready to use for the arrayToDataTable method of Google Charts
def ready_for_arraytodatatable(column_headers, *columns):

    if columns[-1] is None or columns[-1] == []:
        return simplejson.dumps(None)
        
    array_to_data_table = []
    array_to_data_table.append(column_headers)
    if len(columns) > 0:
        for i in range(0, len(columns[0])):
            row = []
            for column in columns:
                row.append(column[i])
            array_to_data_table.append(row)
            
    return simplejson.dumps(array_to_data_table)


# Once we have daily time spent on video and problems, we need to put these informations together
# so that they can be jointly represented in a column chart.
# Thought for ColumnChart of Google Charts.
# Output convenient for Google Charts' arrayToDataTable()  [['day', video_time, problem_time], []]
def join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time):

    days = list(set(video_days + problem_days)) # join days and remove duplicates
    # Check whether neither video watched nor problem tried
    if len(days) <= 0:
        return simplejson.dumps(None)

    days.sort() # order the list
    # list of lists containing date, video time and problem time
    output_array = []
    for i in range(0, len(days)):
        output_array.append([days[i],0,0])
        try: # some video time that day
            auxiliar = video_daily_time[video_days.index(days[i])]
            output_array[i][1] = auxiliar
        except ValueError:
            pass
        try: # some problem time that day
            auxiliar = problem_daily_time[problem_days.index(days[i])]
            output_array[i][2] = auxiliar
        except ValueError:
            pass
    # Insert at the list start the column information
    output_array.insert(0, ['Day', 'Video time (s)', 'Problem time (s)'])
    
    return simplejson.dumps(output_array)

    
def to_iterable_module_id(block_usage_locator):
  
    iterable_module_id = []
    iterable_module_id.append(block_usage_locator.org)
    iterable_module_id.append(block_usage_locator.course)
    #iterable_module_id.append(block_usage_locator.run)
    iterable_module_id.append(block_usage_locator.branch)
    iterable_module_id.append(block_usage_locator.version_guid)
    iterable_module_id.append(block_usage_locator.block_type)
    iterable_module_id.append(block_usage_locator.block_id)    
    
    return iterable_module_id
    

# Converts a list of python datetime objets to a list
# of their equivalent strings
def datelist_to_isoformat(date_list):
  
    return [date.isoformat() for date in date_list]