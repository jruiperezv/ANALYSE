# Functions that query the database for analytics-sensible data

from django.db.models import Q
import math
import re
import simplejson as json
from track.backends.django import TrackingLog

from data_processing import get_current_time, hhmmss_to_secs, to_iterable_module_id, video_events_to_scatter_chart, determine_repetitions_vticks
from models import ConsumptionModule, DailyConsumption, VideoIntervals, VideoEvents
    
##########################################################################
######### TRACKING LOGS DATA QUERYING (data processing purposes)##########
##########################################################################  


############################# VIDEO EVENTS ###############################
 

# Given a video descriptor returns ORDERED the video intervals a student has seen
# A timestamp of the interval points is also recorded.
def find_video_intervals(student, video_module_id):
    INVOLVED_EVENTS = [
        'play_video',
        'seek_video',
    ]
    #event flags to check for duplicity
    play_flag = False # True: last event was a play_videoid
    seek_flag = False # True: last event was a seek_video
    saved_video_flag = False # True: last event was a saved_video_position
    
    interval_start = []
    interval_end = []
    vid_start_time = [] # timestamp for interval_start
    vid_end_time = []   # timestamp for interval_end
    
    iter_video_module_id = to_iterable_module_id(video_module_id)
    #shortlist criteria
    str1 = ';_'.join(x for x in iter_video_module_id if x is not None)
    #DEPRECATED TAG i4x                str2 = ''.join([video_module_id.DEPRECATED_TAG,':;_;_',str1])
    cond1   = Q(event_type__in=INVOLVED_EVENTS, event__contains=video_module_id.html_id())
    cond2_1 = Q(event_type__contains = str1)
    cond2_2 = Q(event_type__contains='save_user_state', event__contains='saved_video_position')
    shorlist_criteria = Q(username=student) & (cond1 | (cond2_1 & cond2_2))
    
    events = TrackingLog.objects.filter(shorlist_criteria)
    if events.count() <= 0:
        # return description: [interval_start, interval_end, vid_start_time, vid_end_time]
        # return list types: [int, int, datetime.date, datetime.date]
        return [0], [0], [], []
    #guarantee the list of events starts with a play_video
    while events[0].event_type != 'play_video':
        events = events[1:]
        if len(events) < 2:
            return [0], [0], [], []
    for event in events:
        if event.event_type == 'play_video':
            if play_flag: # two consecutive play_video events. Second is the relevant one (loads saved_video_position).
                interval_start.pop() #removes last element
                vid_start_time.pop()
            if not seek_flag:
                interval_start.append(eval(event.event)['currentTime'])
                vid_start_time.append(event.time)
            play_flag = True
            seek_flag = False
            saved_video_flag = False
        elif event.event_type == 'seek_video':
            if seek_flag:
                interval_start.pop()
                vid_start_time.pop()
            elif play_flag:
                interval_end.append(eval(event.event)['old_time'])
                vid_end_time.append(event.time)
            interval_start.append(eval(event.event)['new_time'])
            vid_start_time.append(event.time)
            play_flag = False
            seek_flag = True
            saved_video_flag = False
        else: # .../save_user_state
            if play_flag:
                interval_end.append(hhmmss_to_secs(eval(event.event)['POST']['saved_video_position'][0]))
                vid_end_time.append(event.time)
            elif seek_flag:
                interval_start.pop()
                vid_start_time.pop()
            play_flag = False
            seek_flag = False
            saved_video_flag = True
    interval_start = [int(math.floor(val)) for val in interval_start]
    interval_end   = [int(math.floor(val)) for val in interval_end]
    #remove empty intervals (start equals end) and guarantee start < end 
    interval_start1 = []
    interval_end1 = []
    vid_start_time1 = []
    vid_end_time1 = []
    for start_val, end_val, start_time, end_time in zip(interval_start, interval_end, vid_start_time, vid_end_time):
        if start_val < end_val:
            interval_start1.append(start_val)
            interval_end1.append(end_val)
            vid_start_time1.append(start_time)
            vid_end_time1.append(end_time)
        elif start_val > end_val: # case play from video end
            interval_start1.append(0)
            interval_end1.append(end_val)
            vid_start_time1.append(start_time)
            vid_end_time1.append(end_time)            
    # sorting intervals
    if len(interval_start1) <= 0:
        return [0], [0], [], []
    [interval_start, interval_end, vid_start_time, vid_end_time] = zip(*sorted(zip(interval_start1, interval_end1, vid_start_time1, vid_end_time1)))
    interval_start = list(interval_start)
    interval_end = list(interval_end)
    vid_start_time = list(vid_start_time)
    vid_end_time = list(vid_end_time)
    
    # return list types: [int, int, datetime.date, datetime.date]
    return interval_start, interval_end, vid_start_time, vid_end_time    
    

# Obtain list of events relative to videos and their relative position within the video
# For a single student
# CT Current time
# Return format: [[CTs for play], [CTs for pause], [CTs for speed changes], [old_time list], [new_time list]]
# Returns None if there are no events matching criteria
def get_video_events(student, video_module_id):
  
    INVOLVED_EVENTS = [
        'play_video',
        'pause_video',
        'speed_change_video',
        'seek_video'
    ]

    #shortlist criteria
    cond1 = Q(event_type__in=INVOLVED_EVENTS, event__contains=video_module_id.html_id())
    shorlist_criteria = Q(username=student) & cond1
    
    events = TrackingLog.objects.filter(shorlist_criteria)
    if events.count() == 0:
        return None
    
    # List of lists. A list for every event type containing the video relative time    
    events_times = []
    for event in INVOLVED_EVENTS + ['list for seek new_time']:
        events_times.append([])
        
    for event in events:
        currentTime = get_current_time(event)
        events_times[INVOLVED_EVENTS.index(event.event_type)].append(currentTime[0])
        if len(currentTime) > 1: # save new_time for seek_video event
            events_times[-1].append(currentTime[1])
    
    return events_times

    
##########################################################################
############################ PROBLEM EVENTS ##############################
##########################################################################  
    

# Computes the time a student has dedicated to a problem in seconds
#TODO Does it make sense to change the resolution to minutes?
# Returns also daily time spent on a problem by the user
def time_on_problem(student, problem_module_id):
    INVOLVED_EVENTS = [
        'seq_goto',
        'seq_prev',
        'seq_next',
        'page_close'
    ]
    interval_start = []
    interval_end = []
    
    iter_problem_module_id = to_iterable_module_id(problem_module_id)
    #shortlist criteria
    str1 = ';_'.join(x for x in iter_problem_module_id if x is not None)
    #DEPRECATED TAG i4x                str2 = ''.join([problem_module_id.DEPRECATED_TAG,':;_;_',str1])
    cond1 = Q(event_type__in=INVOLVED_EVENTS)
    cond2 = Q(event_type__contains = str1) & Q(event_type__contains = 'problem_get')
    shorlist_criteria = Q(username=student) & (cond1 | cond2)
    
    events = TrackingLog.objects.filter(shorlist_criteria)
    if events.count() <= 0:
        # return description: [problem_time, days, daily_time]
        # return list types: [int, datetime.date, int]
        return 0, [], 0
    
    # Ensure pairs problem_get - INVOLVED_EVENTS (start and end references)
    event_pairs = []
    # Flag to control the pairs. get_problem = True means get_problem event expected
    get_problem = True
    for event in events:
        if get_problem: # looking for a get_problem event
            if re.search('problem_get$',event.event_type) is not None:
                event_pairs.append(event.time)
                get_problem = False
        else:# looking for an event in INVOLVED_EVENTS
            if event.event_type in INVOLVED_EVENTS: 
                event_pairs.append(event.time)
                get_problem = True
    problem_time = 0
    """
    if len(event_pairs) > 0:
        for index in range(0, len(event_pairs), 2):
    """
    i = 0
    while i < len(event_pairs) - 1:        
        time_fraction = (event_pairs[i+1] - event_pairs[i]).total_seconds()
        #TODO Bound time fraction to a reasonable value. Here 2 hours. What would be a reasonable maximum?
        time_fraction = 2*60*60 if time_fraction > 2*60*60 else time_fraction
        problem_time += time_fraction
        i += 2
            
    # Daily info
    days = [event_pairs[0].date()] if len(event_pairs) >= 2 else []
#    for event in event_pairs:
#        days.append(event.date())
    daily_time = [0]
    i = 0
    while i < len(event_pairs) - 1:
        if days[-1] == event_pairs[i].date(): # another interval to add to the same day
            if event_pairs[i+1].date() == event_pairs[i].date(): # the interval belongs to a single day
                daily_time[-1] += (event_pairs[i+1] - event_pairs[i]).total_seconds()
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10. 
                daily_time[-1] += 24*60*60 - event_pairs[i].hour*60*60 - event_pairs[i].minute*60 - event_pairs[i].second
                days.append(event_pairs[i+1].date())
                daily_time.append(event_pairs[i+1].hour*60*60 + event_pairs[i+1].minute*60 + event_pairs[i+1].second)
        else:
            days.append(event_pairs[i].date())
            daily_time.append(0)
            if event_pairs[i+1].date() == event_pairs[i].date(): # the interval belongs to a single day
                daily_time[-1] += (event_pairs[i+1] - event_pairs[i]).total_seconds()
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10.
                daily_time[-1] += 24*60*60 - event_pairs[i].hour*60*60 - event_pairs[i].minute*60 - event_pairs[i].second
                days.append(event_pairs[i+1].date())
                daily_time.append(event_pairs[i+1].hour*60*60 + event_pairs[i+1].minute*60 + event_pairs[i+1].second)            
        i += 2
    return problem_time, days, daily_time

    
    
##########################################################################
######### XINSIDER DATA QUERYING (visualization data for charts) #########
##########################################################################  


# Get info for Video time watched chart
def get_module_consumption(username, course_id, module_type):
  
    #shortlist criteria
    shortlist = Q(student=username, course_key=course_id, module_type = module_type)
    consumption_modules = ConsumptionModule.objects.filter(shortlist)
    module_names = []
    total_times = []    
    video_percentages = []
    for consumption_module in consumption_modules:
        module_names.append(consumption_module.display_name)
        total_times.append(consumption_module.total_time)
        if module_type == u'video':
            video_percentages.append(consumption_module.percent_viewed)
            
    if sum(total_times) <= 0:
        total_times = []
        video_percentages = []
  
    return module_names, total_times, video_percentages


# Get info for Daily time on video and problems chart
# Daily time spent on video and problem resources
def get_daily_consumption(username, course_id, module_type):

    #shortlist criteria
    #shortlist = Q(student=username, course_key=course_id, module_type = module_type)
    try:
        daily_consumption = DailyConsumption.objects.get(student=username, course_key=course_id, module_type = module_type)
        jsonDec = json.decoder.JSONDecoder()
        days = jsonDec.decode(daily_consumption.dates)
        daily_time = jsonDec.decode(daily_consumption.time_per_date)
    except DailyConsumption.DoesNotExist:
        days, daily_time = [], []
    """
    for daily_consumption in daily_consumptions:
        days.append(jsonDec.decode(daily_consumption.dates))
        daily_time.append(jsonDec.decode(daily_consumption.time_per_date))
    """
    return days, daily_time


# Get info for Video events dispersion within video length chart
# At what time the user did what along the video?
def get_video_events_info(username, video_id):
  
    if username == '#average':
        shortlist = Q(module_key = video_id)
    else:
        shortlist = Q(student=username, module_key = video_id)
    video_events = VideoEvents.objects.filter(shortlist)
    jsonDec = json.decoder.JSONDecoder()
    events_times = [[],[],[],[],[]]
    for user_video_events in video_events:
        events_times[0] += jsonDec.decode(user_video_events.play_events)
        events_times[1] += jsonDec.decode(user_video_events.pause_events)
        events_times[2] += jsonDec.decode(user_video_events.change_speed_events)
        events_times[3] += jsonDec.decode(user_video_events.seek_from_events)
        events_times[4] += jsonDec.decode(user_video_events.seek_to_events)
  
    if events_times != [[],[],[],[],[]]:
        scatter_array = video_events_to_scatter_chart(events_times)
    else:
        scatter_array = json.dumps(None)
    
    return scatter_array
    

# Get info for Repetitions per video intervals chart
# How many times which video intervals have been viewed?
def get_user_video_intervals(username, video_id):

    try:
        video_intervals = VideoIntervals.objects.get(student=username, module_key = video_id)
    except VideoIntervals.DoesNotExist:
        return json.dumps(None)
    
    jsonDec = json.decoder.JSONDecoder()
    hist_xaxis = jsonDec.decode(video_intervals.hist_xaxis)
    hist_yaxis = jsonDec.decode(video_intervals.hist_yaxis)
    num_gridlines = 0
    vticks = []
    
    # Interpolation to represent one-second-resolution intervals
    if sum(hist_yaxis) > 0:
        maxRepetitions = max(hist_yaxis)
        num_gridlines = maxRepetitions + 1 if maxRepetitions <= 3 else 5
        vticks = determine_repetitions_vticks(maxRepetitions)
        ordinates_1s = []
        abscissae_1s = list(range(0,hist_xaxis[-1]+1))
        #ordinates_1s.append([])
        for j in range(0,len(hist_xaxis)-1):
            while len(ordinates_1s) <= hist_xaxis[j+1]:
                ordinates_1s.append(hist_yaxis[j])
                
        # array to be used in the arrayToDataTable method of Google Charts
        # actually a list of lists where the first one represent column names and the rest the rows
        video_intervals_array = [['Time (s)', 'Times']]
        for abscissa_1s, ordinate_1s in zip(abscissae_1s, ordinates_1s):
            video_intervals_array.append([str(abscissa_1s), ordinate_1s])
    else:
        video_intervals_array = None
        
    interval_chart_data = {
        'video_intervals_array': video_intervals_array,
        'num_gridlines': num_gridlines,
        'vticks': vticks,
    }    
    
    return json.dumps(interval_chart_data)
