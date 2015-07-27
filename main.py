from __future__ import division
import cv2
import time
import math
import random

from naoqi import ALProxy
from naoqi import ALBroker

import gaze
import display
from confidence import Confidence

# set robot connection values
IP = 'bobby.local'
PORT = 9559

# create broker to construct NAOqi module and listen to other modules
broker = ALBroker("broker",
    "0.0.0.0",  # listen to anyone
    0,          # find a free port and use it
    IP,         # parent broker IP
    PORT)       # parent broker port

# create proxies
motion = ALProxy("ALMotion")
tts = ALProxy("ALTextToSpeech")
face_tracker = ALProxy("ALFaceTracker")
posture = ALProxy("ALRobotPosture")
gaze_analysis = ALProxy("ALGazeAnalysis")

# set game time limit
max_game_time = 15

# set object angles, error, and confidences
object_angles = [-30, -10, -9, 15, 40]
object_angle_error = math.radians(15)
confidences = Confidence(object_angles, object_angle_error)

# get into starting position (sitting down, looking up towards person)
motion.setStiffnesses("Body", 1.0)
posture.goToPosture("Crouch", 0.2)
motion.setAngles("HeadPitch", math.radians(-10), 0.2)

# give robot some time to get to this angle before starting face tracker
time.sleep(0.5)

# subscribe to gaze analysis
gaze_analysis.setTolerance(1)
gaze_analysis.subscribe("_")

# start face tracker
face_tracker.setWholeBodyOn(False)
face_tracker.startTracker()
print 'Face tracker successfully started!'

# wait a little to let robot find face
time.sleep(0.5)

# get person ID
person_id = gaze.getPersonID()

person_gaze_pitch_adjustment = gaze.getPersonGazePitchAdjustment(person_id)
print "person_gaze_pitch_adjustment:", person_gaze_pitch_adjustment

# finish talking
tts.say("Okay, let's play!")

# set timer
timeout = time.time() + max_game_time

# while 'q' is not pressed and time limit isn't reached
while (cv2.waitKey(1) & 0xFF != ord('q')) and (time.time() < timeout):

    try:
        # get person gaze data
        person_gaze = gaze.getPersonGaze(person_id, person_gaze_pitch_adjustment)

    # if gaze data can't be retrieved for that person ID anymore (e.g. if bot entirely loses track of person)
    except RuntimeError:
        # print "Couldn't get gaze direction and head angles for that ID"
        
        # get new people IDs
        person_id = gaze.getPersonID()

    # if gaze direction or head angles are empty lists (e.g. if person's gaze is too steep)
    except IndexError:
        # print "Gaze data was empty list"
        pass

    else:
        # get person location data
        person_location = gaze.getPersonLocation(person_id)
        
        # if person gaze is near the objects
        if gaze.personLookingAtObjects(person_gaze, person_location):

            gaze_location = gaze.getObjectLocation(person_gaze, person_location, debug = True)
            print gaze_location

            gaze_angle = gaze_location[3]

            confidences.update(gaze_angle, debug = True)

    # get image from nao and display
    video.show()

# unsubscribe from gaze analysis
gaze_analysis.unsubscribe("_")

# stop face tracker
face_tracker.stopTracker()
print "Face tracker stopped."

display.close()
confidences.normalize()
confidences.guess()

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# remove stiffness
motion.setStiffnesses("Body", 0.0)