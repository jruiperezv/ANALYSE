This repository contains the Open edX platform release "hotfix-2014-11-17" with ANALYSE module.

Overview of ANALYSE
------------------

ANALYSE is learning analytics tool developed for Open edX. This is a beta release which extends the learning analytics functionality of Open edX with 12 new visualizations. A new tab has been addded in the course dashboard to access ANALYSE. Some of the features are the next:

<ul>
<li>The learning analytics dashboard has 3 visualizations related to exercises, 4 related to videos and 5 related to general course activity</li>
<li>The instructors of a course can access the information about the aggregate of all students in a course an also each student individually. That allows instructor to keep track about how the course is progressing and control each student separately</li>
<li>The students in a course can access their own information only which can be used for self-awareness and reflect on their learning process</li>
<li>The different indicators are processed in background in regular intervals of time as schedule jobs by the use of Celery Beat</li>
</ul>

Installation
------------
For the installation of ANALYSE you can either:

<ul>
<li>Use this full repository of Open edX which has the both the "hotfix-2014-11-17" release and ANALYSE module</li>
<li>Take ANALYSE code and insert it in a different Open edX release. Although we cannot guarantee that there will be no problems.
</ul>

The functionality of ANALYSE has been added as a new django application. The different files and folders added for ANALYSE are the next:
<ul>
<li>/lms/djangoapps/learning_analytics/*</li>
<li>/lms/static/js/learning_analytics/*</li>
<li>/lms/static/sass/course/learning_analytics/_learning_analytics.scss</li>
<li>/lms/templates/learning_analytics/*</li>
<li>/lms/envs/devstack_analytics.py</li>
</ul>
The files from Open edX that has been modified to introduce ANALYSE:
<li>/common/lib/xmodule/xmodule/tabs.py</li>
<li>/lms/static/sass/course.scss.mako</li>
<li>/lms/urls.py</li>

Celery Beat needs to be activated and configured so that it run the task which updates the indicators in background.

License
-------

The code in this repository is licensed under version 3 of the AGPL unless
otherwise noted. Please see the
[`LICENSE`](https://github.com/edx/edx-platform/blob/master/LICENSE) file
for details with. The next additional term should be also taken into account:
</br>
<ul style="text-align: justify">
<li>
Required to preserve the author attributions on the new added work for the development of ANALYSE
</li>
</ul>

Getting Help
------------

If you're having trouble with the installation or how to use ANALYSE feel free to <a href="mailto:jruipere@it.uc3m.es">contact</a> and we will do our best to help you out.

Contributions are welcomed
-----------------

If you are interested in contributing to the development of ANALYSE we will be happy to help. For bug solving changes feel free to send a pull request. In case you would like to make a major change or to develop new functionality, please <a href="mailto:jruipere@it.uc3m.es">contact</a> before starting your development, so that we can find the best way to make it work.


Developed by
--------------
<p> ANALYSE has been developed in the <a href="http://gradient.it.uc3m.es/">Gradient</a> lab, which is the e-learning laboratory inside the <a href="http://www.gast.it.uc3m.es/">GAST</a> group, as a part of the <a href="http://www.it.uc3m.es/vi/">Department of Telematic Engineering</a>, at the <a href="http://www.uc3m.es/">University Carlos III of Madrid</a> (Spain). The main people involved in the design and implementation of this tool have been the following: </p>
<ul style="text-align: justify" value="circle">
<li>
	José Antonio Ruipérez Valiente - IMDEA Networks Institute and Universidad Carlos III de Madrid- jruipere@it.uc3m.es
	</li>
	<li>
	Pedro Jose Muñoz Merino - Universidad Carlos III de Madrid - pedmume@it.uc3m.es
	</li>
	<li>
	Héctor Javier Pijeira Díaz - Universidad Carlos III de Madrid (by implementing his Final Year Project)
	</li>
	<li>
	Javier Santofimia Ruiz - Universidad Carlos III de Madrid (by implementing his Final Year Project)
	</li>
	<li>
	Carlos Delgado Kloos - Universidad Carlos III de Madrid
	</li>
	</ul>
Acknowledgements. This work has been supported by:
<ul>
<li>
The "eMadrid" project (Regional Government of Madrid) under grant S2013/ICE-2715
</li>
 <li>
The RESET project (Ministry of Economy and Competiveness) under grant TIN2014-53199-C3-1-R
</li>
	</ul>
