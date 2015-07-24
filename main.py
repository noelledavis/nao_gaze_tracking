from __future__ import division
import cv2
import time
import math
import random

from naoqi import ALProxy
from naoqi import ALBroker

import images
import gaze

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
camera = ALProxy("ALVideoDevice")
motion = ALProxy("ALMotion")
tts = ALProxy("ALTextToSpeech")
face_tracker = ALProxy("ALFaceTracker")
posture = ALProxy("ALRobotPosture")
gaze_analysis = ALProxy("ALGazeAnalysis")

# set nao camera values
cam_num = 0
resolution = 2
colorspace = 13
fps = 10

# set game time limit
max_game_time = 15

# lists of object angles and confidences
object_angles = [-30, -10, -9, 15, 40]
object_angles = [math.radians(angle) for angle in object_angles]
object_confidences = [0] * len(object_angles)

# set angle error in rad for determining which object(s) person is looking at
object_angle_error = math.radians(15)

# set brightness to default
camera.setCameraParameterToDefault("python_client", 0)

# subscribe to camera
video_client = camera.subscribeCamera("python_client", cam_num, resolution, colorspace, fps)

# stiffen whole body
motion.setStiffnesses("Body", 1.0)

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# tilt head up to look at person
motion.setAngles("HeadPitch", math.radians(-10), 0.2)

# give robot some time to get to this angle before starting face tracker
time.sleep(0.5)

# set face tracker to use only head, not whole body
face_tracker.setWholeBodyOn(False)

# subscribe to gaze analysis
gaze_analysis.subscribe("_")

# set high tolerance for thinking that person is looking at robot so it's easy to get people IDs
gaze_analysis.setTolerance(1)

# start face tracker
face_tracker.startTracker()
print 'Face tracker successfully started!'

# wait a little to let robot find face
time.sleep(0.5)

# get people IDs
people_ids = gaze.getPeopleIDs()

# take ID of first person in list
person_id = people_ids[0]

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
        people_ids = gaze.getPeopleIDs()
        person_id = people_ids[0]

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
            
            # for count and angle of each object
            for i, object_angle in enumerate(object_angles):

                # if gaze angle is within object_angle_error of the object angle on either side
                if abs(object_angle - gaze_angle) <= object_angle_error:
                    
                    # add 1 to the confidence for that object
                    object_confidences[i] += 1

                    print "\t", math.degrees(object_angle),

            print

    # get image from nao
    nao_image = camera.getImageRemote(video_client)

    # display image with opencv
    images.showWithOpenCV(nao_image)

# print object_confidences
print object_confidences

# unsubscribe from gaze analysis
gaze_analysis.unsubscribe("_")

# stop face tracker
face_tracker.stopTracker()
print "Face tracker stopped."

# unsubscribe from camera
camera.unsubscribe(video_client)

cv2.destroyAllWindows()

# if all confidences are zero
if not all(confidence == 0 for confidence in object_confidences):

    # normalize confidences to values in the range [0, 100]
    object_confidences = [confidence / max(object_confidences) * 100 for confidence in object_confidences]

    # communicate confidences for each object
    print "Object confidences:", object_confidences

    # determine which objects have highest confidence levels
    max_confidence = max(object_confidences)
    best_object_indices = [i for i, confidence in enumerate(object_confidences) if confidence == max_confidence]

    for i in best_object_indices:
        print "Are you thinking of object " + str(i) + ', the one at ' + str(math.degrees(object_angles[i])) + " degrees?"
        motion.setAngles("HeadYaw", object_angles[i], 0.2)
        motion.setAngles("HeadPitch", math.radians(15), 0.2)
        time.sleep(3)

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# remove stiffness
motion.setStiffnesses("Body", 0.0)