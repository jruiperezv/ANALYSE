import ast

from xmodule.modulestore.django import modulestore
from xmodule.course_module import CourseDescriptor
from submissions import api as sub_api
from student.models import anonymous_id_for_user
import xmodule.graders as xmgraders
from courseware.models import StudentModule
from student.models import CourseEnrollment, CourseAccessRole
from django.contrib.auth.models import User
from contextlib import contextmanager
from django.db import transaction
from courseware.module_render import get_module_for_descriptor
from courseware.model_data import FieldDataCache
from django.test.client import RequestFactory
from track.models import TrackingLog
from eventtracking import tracker 
from opaque_keys.edx.locations import SlashSeparatedCourseKey, Location
from opaque_keys.edx.locator import CourseLocator, BlockUsageLocator
from instructor.utils import get_module_for_student
from django.utils import timezone
import datetime

def get_courses_list():
        """
        Return a list with all course modules
        """
        return modulestore().get_courses()
        
def get_course_key(course_id):
    """
    Return course opaque key from olf course ID
    """
    # Get course opaque key
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    return course_key


def get_course_module(course_key):
    """
    Return course module 
    """
    # Get course module
    course = modulestore().get_course(course_key)
    return course


def get_course_struct(course):
    """
    Return a dictionary with the course structure of all chapters, sequentials,
    and verticals modules with their names and usage_keys
    
    course: course module
    
    """
    course_key = course.id
    course_struct = {'id': course_key,
                     'name': course.display_name_with_default,
                     'chapters': [] }
    # Chapters
    for chapter in course.get_children():
        if chapter.category == 'chapter':
            released = (timezone.make_aware(datetime.datetime.now(), timezone.get_default_timezone()) > 
                              chapter.start)
            chapter_struct = {'id': chapter.location,
                                         'name': chapter.display_name_with_default,
                                         'sequentials': [],
                                         'released': released }
            chapter_graded = False
            # Sequentials
            for sequential in chapter.get_children():
                if sequential.category == 'sequential':
                    seq_struct = {'id': sequential.location,
                                  'name': sequential.display_name_with_default,
                                  'graded': sequential.graded,
                                  'verticals': [],
                                  'released':released }
                    if seq_struct['graded']:
                        chapter_graded = True
                    # Verticals
                    for vertical in sequential.get_children():
                        if vertical.category == 'vertical':
                            vert_struct = {'id': vertical.location,
                                           'name': vertical.display_name_with_default,
                                           'graded': vertical.graded,
                                           'released': released }
                            seq_struct['verticals'].append(vert_struct)
                    chapter_struct['sequentials'].append(seq_struct)
            chapter_struct['graded'] = chapter_graded
            course_struct['chapters'].append(chapter_struct)
    
    return course_struct


def get_course_grade_cutoff(course):
    return course.grade_cutoffs['Pass']


def get_course_students(course_key):
    """
    Obtain students id in the course and return their User object
    """
    students_id = (CourseEnrollment.objects
        .filter(course_id=course_key)
        .values_list('user_id', flat=True))
    students = User.objects.filter(id__in=students_id)
    return students

def dump_full_grading_context(course):
    """
    Render information about course grading context
    Returns all sections    
    """

    weight_subs = []
    subsections = []
    # Get sections in each weighted subsection (Homework, Lab or Exam)
    if isinstance(course.grader, xmgraders.WeightedSubsectionsGrader):
        gcontext = course.grading_context['graded_sections']
        for subgrader, category, weight in course.grader.sections:
            # Add weighted section to the list
            weight_subs.append({'type':subgrader.type, 'category':category, 'weight':weight})
            
            # # TODO: MIRAR QUE PASA CON LAS SECCIONES QUE SALEN EN EL GRAD_CONTEXT 
            # # PERO NO EN SUBGRADERS
            if gcontext.has_key(category):
                for i in range(max(subgrader.min_count, len(gcontext[category]))):
                    if subgrader.min_count > 1:
                        label = subgrader.short_label + ' ' + str(subgrader.starting_index + i)
                    else:
                        label = subgrader.short_label
                    if i < len(gcontext[category]):
                        section_descriptor = gcontext[category][i]['section_descriptor']
                        problem_descriptors = gcontext[category][i]['xmoduledescriptors']
                        # See if section is released
                        released = (timezone.make_aware(datetime.datetime.now(), timezone.get_default_timezone()) > 
                                                                        section_descriptor.start)
                        
                        subsections.append({'category':category,
                                              'label':label,
                                              'released':released,
                                              'name': section_descriptor.display_name,
                                              'problems': problem_descriptors,
                                              'max_grade': section_max_grade(course.id, problem_descriptors)})
                    else:
                        subsections.append({'category':category,
                                              'label':label,
                                              'released':False,
                                              'name': category + ' ' + str(subgrader.starting_index + i) + ' Unreleased',
                                              'problems': [],
                                              'max_grade': 0})
            else:
                # Subsection Unreleased
                for i in range(subgrader.min_count):
                    subsections.append({'category':category,
                                          'label':subgrader.short_label + ' ' + str(subgrader.starting_index + i),
                                          'released':False,
                                          'name': category + ' ' + str(subgrader.starting_index + i) + ' Unreleased',
                                          'problems': [],
                                          'max_grade': 0})
                            
    elif isinstance(course.grader, xmgraders.SingleSectionGrader):
        # Single section
        gcontext = course.grading_context['graded_sections']
        singlegrader = course.grader
        # Add weighted section to the list
        weight_subs.append({'type':singlegrader.type, 'category':singlegrader.category, 'weight':1})
        
        if gcontext.has_key(singlegrader.category):
            section_descriptor = gcontext[singlegrader.category][0]['section_descriptor']
            problem_descriptors = gcontext[singlegrader.category][0]['xmoduledescriptors']
            # See if section is released
            released = (timezone.make_aware(datetime.datetime.now(), timezone.get_default_timezone()) > 
                                                section_descriptor.start)
            subsections.append({'category':singlegrader.category,
                                'label':singlegrader.short_label,
                                'released':True,
                                'name': section_descriptor.display_name,
                                'problems': problem_descriptors,
                                'max_grade': section_max_grade(course.id, problem_descriptors)})
        else:
            # Subsection Unreleased
            subsections.append({'category':singlegrader.category,
                                'label':singlegrader.short_label,
                                'released':False,
                                'name': category + ' Unreleased',
                                'problems': [],
                                'max_grade': 0})
        
    dump_full_graded = {'weight_subsections':weight_subs, 'graded_sections':subsections}
    return dump_full_graded

        
def section_max_grade(course_key, problem_descriptors):
    """
    Return max grade a student can get in a series of problem descriptors
    """
    max_grade = 0
   
    students_id = CourseEnrollment.objects.filter(course_id=course_key)
    if students_id.count() == 0:
        return max_grade
       
    instructors = CourseAccessRole.objects.filter(role='instructor')
    if instructors.count() > 0:
            instructor = User.objects.get(id=instructors[0].user.id)
    else:
            ## TODO SEND WARNING BECAUSE COURSE HAVE NO INSTRUCTOR
                instructor = students_id[0].user 
    
    for problem in problem_descriptors:
        score = get_problem_score(course_key, instructor, problem)
        if score is not None and score[1] is not None:
            max_grade += score[1]
                
    return max_grade      


def is_problem_done(course_key, user, problem_descriptor):
    """
    Return if problem given is done
    
    course_key: course opaque key
    user: a Student object
    problem_descriptor: an XModuleDescriptor
    """
    problem_grade = get_problem_score(course_key, user, problem_descriptor)[0]  # Get problem score (dont care total)
    if problem_grade:
        return True
    else:
        return False  # StudentModule not created yet (not done yet) or problem not graded
    
    
def get_problem_score(course_key, user, problem_descriptor):
    """
    Return problem score as a tuple (score, total).
    Score will be None if problem is not yet done.
    Based on courseware.grades get_score function.
    
    course_key: course opaque key
    user: a Student object
    problem_descriptor: an XModuleDescriptor

    """
    # some problems have state that is updated independently of interaction
    # with the LMS, so they need to always be scored. (E.g. foldit.)
    if problem_descriptor.always_recalculate_grades:
        problem_mod = get_module_for_student(user, problem_descriptor.location)
        if problem_mod is None:
            return (None, None)
        score = problem_mod.get_score()
        if score is not None:
            if score['total'] is None:
                return (None, problem_mod.max_score())
            elif score['score'] == 0:
                progress = problem_mod.get_progress()
                if progress is not None and progress.done():
                    return(score['score'], score['total'])
                else:
                    return (None, score['total']) 
            else:
                return(score['score'], score['total'])
        else:
            return (None, problem_mod.max_score())

    if not problem_descriptor.has_score:
        # These are not problems, and do not have a score
        return (None, None)

    try:
        student_module = StudentModule.objects.get(
            student=user,
            course_id=course_key,
            module_state_key=problem_descriptor.location
        )
    except StudentModule.DoesNotExist:
        student_module = None

    if student_module is not None and student_module.max_grade is not None:
        correct = student_module.grade
        total = student_module.max_grade
    else:
        # If the problem was not in the cache, or hasn't been graded yet,
        # we need to instantiate the problem.
        # Otherwise, the max score (cached in student_module) won't be available
        problem_mod = get_module_for_student(user, problem_descriptor.location)
        if problem_mod is None:
            return (None, None)

        correct = None
        total = problem_mod.max_score()

        # Problem may be an error module (if something in the problem builder failed)
        # In which case check if get_score() returns total value
        if total is None:
            score = problem_mod.get_score()
            if score is None:
                return (None, None)
            else:
                total = score['total']

    # Now we re-weight the problem, if specified
    weight = problem_descriptor.weight
    if weight is not None:
        if total == 0:
            return (correct, total)
        if correct is not None:
            correct = correct * weight / total
        total = weight
        
    return (correct, total)
   
   
def get_course_events_sql(course_key, student):
    """
    Returns course events stored in tracking log for
    given course and student
    
    course_key: Course Opaque Key
    student: student object or student username as string
    """
    
    events = TrackingLog.objects.filter(username=student).order_by('time')
    # Filter events with course_key
    # TODO: More event types?
    filter_id = []
    for event in events:
        # Filter browser events with course_key
        if event.event_source == 'browser':
            if ((event.event_type == 'seq_goto' or 
                event.event_type == 'seq_next' or 
                event.event_type == 'page_close' or
                event.event_type == 'show_transcript' or
                event.event_type == 'load_video') and
                is_same_course(event.page, course_key)):
                filter_id.append(event.id)

        # Filter server events with course_id
        elif event.event_source == 'server':
            split_url = filter(None, event.event_type.split('/'))
            if len(split_url) != 0: 
                if split_url[-1] == 'logout':
                    filter_id.append(event.id)
                elif split_url[-1] == 'dashboard':
                    filter_id.append(event.id)
                elif is_same_course(event.event_type, course_key):
                    filter_id.append(event.id)

    events = events.filter(id__in=filter_id)
    return events
    

def get_course_access_events_sql(course_key, student):
    """
    Returns course events stored in tracking log for
    course access
    course_key: Course Opaque Key
    student: student object or student username as string
    """
    events = TrackingLog.objects.filter(username=student).order_by('time')
    # Filter events with course_key
    filter_id = []
    for event in events:
        # Filter browser events with course_key
        if event.event_source == 'browser':
            if ((event.event_type == 'seq_prev' or 
                 event.event_type == 'seq_next' or
                 event.event_type == 'seq_goto') and
                 is_same_course(event.page, course_key)):
                filter_id.append(event.id)
                
        # Filter server events with course_id
        elif event.event_source == 'server':
            split_url = filter(None, event.event_type.split('/'))
            if len(split_url) != 0: 
                if split_url[0] == 'courses':
                    if (is_same_course(event.event_type, course_key) and 
                        not is_xblock_event(event) and
                        get_locations_from_url(event.event_type)[1] is not None):
                        filter_id.append(event.id)
                                
    events = events.filter(id__in=filter_id)
    return events


def is_same_course(course_1, course_2):
    """
    Compares 2 courses in any format (course_key, string,
    unicode, string or unicode with course on it, etc).
    Returns true if both are the same course and false in
    any other case
    """
    # Get course 1 key
    if (course_1.__class__ == SlashSeparatedCourseKey or
            course_1.__class__ == CourseLocator):
        course_1_key = course_1
    elif course_1.__class__ == str or course_1.__class__ == unicode:
        course_1_key = get_course_from_url(course_1)
        if course_1_key == None:
            return False
    else:
        # TODO: Check if is course module
        return False
    
    # Get course 2 key
    if (course_2.__class__ == SlashSeparatedCourseKey.__class__ or
            course_2.__class__ == CourseLocator):
        course_2_key = course_2
    elif course_2.__class__ == str or course_2.__class__ == unicode:
        course_2_key = get_course_from_url(course_2)
        if course_2_key == None:
            return False
    else:
        # TODO: Check if is course module
        return False
    
    if course_1_key == course_2_key:
        return True
    else:
        return False
     
         
def get_course_from_url(url):
    """
    Return course key from an url that can be an old style
    course ID, or a url with old style course ID contained on
    it. Returns None if no course is find
    """
    split_url = filter(None, url.split('/'))
    if len(split_url) < 3:
        # Wrong string
        return None
    elif len(split_url) == 3:
        # Old style course id
        return get_course_key('/'.join(split_url))
    else:
        # Search if course ID is contained in url
        course_index = 0
        for sect in split_url:
            course_index += 1
            if sect == 'courses':
                break
        if len(split_url) > course_index + 2:
            return get_course_key('/'.join(split_url[course_index:course_index + 3]))
        
    return None


def get_locations_from_url(url, course_blocks=None):
    """
    Return sequential, chapter and course keys from
    given url if there is any
    
    Return (course key, chapter key, sequential key)
    """
    # Get route
    split_url = filter(None, url.split('/'))
    course_index = 0
    for sect in split_url:
        course_index += 1
        if sect == 'courses':
            break
    route = split_url[course_index:]
    if len(route) < 3:
        # No course in url
        return (None, None, None)
    else:
        course_key = get_course_key('/'.join(route[0:3]))
        if len(route) < 5 or route[3] != 'courseware':
            # No sequential or chapter
            if len(route) > 3 and route[3] == 'xblock':
                xblock_id = filter(None, route[4].split(';_'))[-1]
                if course_blocks is None:
                    course_blocks = get_course_blocks(get_course_module(course_key))
                    
                if course_blocks.has_key(xblock_id):
                    return (course_key, course_blocks[xblock_id]['chapter'], course_blocks[xblock_id]['sequential'])
                else:
                    return (course_key, None, None)
            else:
                return (course_key, None, None)
        elif len(route) == 5:
            # Only chapter
            chapter_key = course_key.make_usage_key('chapter', route[4])
            return (course_key, chapter_key, None)
        else:
            # Chapter and sequential
            chapter_key = course_key.make_usage_key('chapter', route[4])
            sequential_key = course_key.make_usage_key('sequential', route[5])
            return (course_key, chapter_key, sequential_key)
        
        
def compare_locations(loc1, loc2, course_key=None):
    """
    Compare if is same location in a certain course
    due to opaque keys sometimes comparaisions are not ok
    """
    if loc1 == loc2: return True
    
    if course_key is None:
        if loc1.__class__ == Location or loc1.__class__ == BlockUsageLocator:
            course_key = loc1.course_key
        elif loc2.__class__ == Location or loc2.__class__ == BlockUsageLocator:
            course_key = loc2.course_key
        else:
            return False
        
    if loc1.__class__ == Location or loc1.__class__ == BlockUsageLocator:
        lockey1 = loc1
    elif loc1.__class__ == str or loc1.__class__ == unicode:
        lockey1 = course_key.make_usage_key_from_deprecated_string(loc1)
    else:
        return False
    
    if loc2.__class__ == Location or loc2.__class__ == BlockUsageLocator:
        lockey2 = loc2
    elif loc2.__class__ == str or loc2.__class__ == unicode:
        lockey2 = course_key.make_usage_key_from_deprecated_string(loc2)
    else:
        return False
        

    return lockey1.to_deprecated_string() == lockey2.to_deprecated_string()
   
   
def get_course_blocks(course):
    blocks = {}
    
    for chapter in course.get_children():
        for seq in chapter.get_children():
            for vert in seq.get_children():
                for block in vert.get_children():
                    blocks[block.location.block_id] = {'chapter':chapter.location,
                                                       'sequential':seq.location,
                                                       'block':block.location}
    return blocks


def is_xblock_event(event):
    if event.event_source != 'server':
        return False

    # Get route
    split_url = filter(None, event.event_type.split('/'))
    course_index = 0
    for sect in split_url:
        course_index += 1
        if sect == 'courses':
            break
    route = split_url[course_index:]
    
    if len(route) > 3 and route[3] == 'xblock':
        return True
    else:
        return False
