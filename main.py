from __future__ import division
import cv2
import time
import math
import random

from naoqi import ALProxy
from naoqi import ALBroker

import robot
from gaze import Gaze
from confidence import Confidence

robot.connect()

# create proxies
motion = ALProxy("ALMotion")
face_tracker = ALProxy("ALFaceTracker")
posture = ALProxy("ALRobotPosture")

# set game time limit
max_game_time = 15

object_yaws = []
object_pitches = []

object_angle_file = open("object_angles.txt")
for object_angle in object_angle_file:
	yaw, pitch = object_angle.split(', ')
	object_yaws.append(float(yaw))
	object_pitches.append(float(pitch))

# set object angles, error, and confidences
object_angle_error = math.radians(15)
confidences = Confidence(object_yaws, object_angle_error)

# get into starting position (sitting down, looking up towards person)
motion.setStiffnesses("Body", 1.0)
posture.goToPosture("Crouch", 0.2)
motion.setAngles("HeadPitch", math.radians(-10), 0.2)

# give robot some time to get to this angle before starting face tracker
time.sleep(0.5)

# start face tracker
face_tracker.setWholeBodyOn(False)
face_tracker.startTracker()
print 'Face tracker successfully started!'

# wait a little to let robot find face
time.sleep(0.5)

gaze = Gaze()

gaze.findPersonPitchAdjustment()

# set timer
timeout = time.time() + max_game_time

# while 'q' is not pressed and time limit isn't reached
while time.time() < timeout:

	gaze_location = gaze.getObjectLocation()
	
	# if can't get location of person's gaze or if it's not near the objects
	if gaze_location is None:
		continue

	confidences.update(gaze.robot_object_yaw)

gaze.stop()

# stop face tracker
face_tracker.stopTracker()
print "Face tracker stopped."

confidences.normalize()
confidences.guess()

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# remove stiffness
motion.setStiffnesses("Body", 0.0)