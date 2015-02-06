class UserVideoIntervals:
  
    def __init__(self, student, video_id, interval_start, interval_end, 
                 vid_start_time, vid_end_time, disjointed_start, disjointed_end):
        self.student = student
        self.video_id = video_id
        self.interval_start = interval_start
        self.interval_end = interval_end      
        self.vid_start_time = vid_start_time
        self.vid_end_time = vid_end_time
        self.disjointed_start = disjointed_start
        self.disjointed_end = disjointed_end

    def __repr__(self):
        return 'UserVideoIntervals<%r>' % ({
            'student': self.student,
            'video_id': self.video_id,
            'interval_start': self.interval_start,
            'interval_end': self.interval_end,
            'vid_start_time': self.vid_start_time,
            'vid_end_time': self.vid_end_time,
            'disjointed_start': self.disjointed_start,
            'disjointed_end': self.disjointed_end, 
        },)
            
    def __unicode__(self):
        return unicode(repr(self))        
        
class UserTimeOnProblems:
  
    def __init__(self, student, problem_id, problem_time, days, daily_time):
        self.student = student
        self.problem_id = problem_id
        self.problem_time = problem_time
        self.days = days
        self.daily_time = daily_time
        
    def __repr__(self):
        return 'UserTimeOnProblems<%r>' % ({
            'student': self.student,
            'problem_id': self.problem_id,
            'problem_time': self.problem_time,
            'days': self.days,
            'daily_time': self.daily_time,         
        },)
            
    def __unicode__(self):
        return unicode(repr(self))        