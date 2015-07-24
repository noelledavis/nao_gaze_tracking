from __future__ import division
import cv2
import time
import math
import random

from naoqi import ALProxy
from naoqi import ALModule
from naoqi import ALBroker

import images

def rad2deg(rad):
    if isinstance(rad, list):
        deg = []
        for angle in rad:
            deg.append(rad2deg(angle))
    else:
        deg = int(round(rad * 180 / math.pi))

    return deg

def deg2rad(deg):
    if isinstance(deg, list):
        rad = []
        for angle in deg:
            rad.append(deg2rad(angle))
    else:
        rad = deg * math.pi / 180

    return rad

def getPeopleIDs(debug = False):
    """ Tries to get people IDs, then if none are retrieved, tries again every 0.5 seconds until it gets some. """

    # try to get list of IDs of people looking at robot
    people_ids = memory.getData("GazeAnalysis/PeopleLookingAtRobot")
    
    # if robot hasn't gotten any people IDs
    while people_ids is None or len(people_ids) == 0:

        # wait a little bit
        time.sleep(0.5)

        # get list of IDs of people looking at robot
        people_ids = memory.getData("GazeAnalysis/PeopleLookingAtRobot")

    if debug:
        print "Done! About to return these people IDs:", people_ids

    return people_ids

def getRawPersonGaze(person_id):
    """ Returns person's gaze a a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively.
    Bases gaze on both eye and head angles. Does not compensate for variable robot head position. """

    # retrieve GazeDirection and HeadAngles values
    gaze_dir = memory.getData("PeoplePerception/Person/" + str(person_id) + "/GazeDirection")
    head_angles =  memory.getData("PeoplePerception/Person/" + str(person_id) + "/HeadAngles")
    
    # extract gaze direction and head angles data
    person_eye_yaw = gaze_dir[0]
    person_eye_pitch = gaze_dir[1]
    
    person_head_yaw = head_angles[0]
    person_head_pitch = head_angles[1]

    # combine eye and head gaze values
    person_gaze_yaw = -(person_eye_yaw + person_head_yaw) # person's left is (-), person's right is (+)
    person_gaze_pitch = person_eye_pitch + person_head_pitch + math.pi / 2 # all the way up is pi, all the way down is 0
    
    return [person_gaze_yaw, person_gaze_pitch]

def getAveragePitchOverTime(person_id, time_limit):
    """ Gets average pitch of the person's gaze relative to the robot over the specified amount of time 
    and only of instances when the pitch is within the range. Will automatically update person ID if needed. """

    pitch_sum = 0
    pitch_count = 0

    timeout = time.time() + time_limit

    while time.time() < timeout:

            
        try:
            # get person gaze data
            person_gaze = getRawPersonGaze(person_id)

        # if gaze data can't be retrieved for that person ID anymore (e.g. if bot entirely loses track of person)
        except RuntimeError:
            print "Couldn't get gaze direction and head angles for that ID"
            
            # get new people IDs
            people_ids = getPeopleIDs()
            person_id = people_ids[0]

        # if gaze direction or head angles are empty lists (e.g. if person's gaze is too steep)
        except IndexError:
            print "Gaze data was empty list"

        else:
            person_gaze_yaw, person_gaze_pitch = person_gaze

            # if pitch is within the range (i.e. person is looking at robot's head)
            if abs(person_gaze_yaw - 0) < deg2rad(15) and abs(person_gaze_pitch - deg2rad(90)) < deg2rad(20):
                pitch_sum += person_gaze_pitch
                pitch_count += 1

    if pitch_sum == 0:
        return None

    pitch_avg = pitch_sum / pitch_count

    return pitch_avg

def getPersonGazePitchAdjustment(person_id):
    """ Returns the adjustment needed to be made to measured gaze pitch values. Gets the person's attention 
    to record his gaze pitch values during eye contact by speaking. """

    # get person to look directly at eyes
    tts.post.say("Hi there! My name is Bobby. What's your name?")

    # try to get average pitch of instances where person is looking at robot
    control_pitch = getAveragePitchOverTime(person_id, 3)
    time.sleep(1)

    # finish talking
    tts.say("Nice to meet you!")
    time.sleep(1)

    # list of stalling phrases to try to get person to look at robot
    stalls = ["I'm so excited!",
        "This will be lots of fun!",
        "I Spy is my favorite game ever.",
        "I love playing I Spy!",
        "I am so ready to play!",
        "We're going to have so much fun playing.",
        "I Spy is so much fun."]

    # index to iterate through stalling phrases
    index = 0

    # shuffle stalling phrases
    random.shuffle(stalls)

    # while control_pitch is None (robot couldn't get average pitch)
    while control_pitch is None:
        tts.post.say(stalls[index])
        control_pitch = getAveragePitchOverTime(person_id, 3)
        index += 1

        # if we've gone through all the stalls, shuffle them and start over
        if index == len(stalls):
            index = 0
            random.shuffle(stalls)

    # the pitch adjustment we need to make is the difference between (the measured value at 90 degrees) and (90 degrees)
    person_gaze_pitch_adjustment = control_pitch - deg2rad(90)

    return person_gaze_pitch_adjustment

def getRobotHeadAngles():

    # retrieve robot head angles
    robot_head_angles = motion.getAngles("Head", False)

    # unpack robot head angles
    robot_head_yaw = robot_head_angles[0] # left (+) and right (-)
    robot_head_pitch = -robot_head_angles[1] # all the way up (+) and all the way down (-), see http://doc.aldebaran.com/2-1/family/robots/joints_robot.html

    # return adjusted robot head angles
    return [robot_head_yaw, robot_head_pitch]

def getPersonGaze(person_id, person_gaze_pitch_adjustment):
    """ Returns person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively. 
    Gets gaze from getRawPersonGaze function, then compensates for variable robot head position and measured pitch inaccuracy. """

    person_gaze_yaw, person_gaze_pitch = getRawPersonGaze(person_id)

    robot_head_yaw, robot_head_pitch = getRobotHeadAngles()
    
    # compensate for variable robot head angles
    person_gaze_yaw -= robot_head_yaw # person's left is (-), person's right is (+)
    person_gaze_pitch -= robot_head_pitch # all the way up is pi, all the way down is 0

    # compensate for measured pitch inaccuracy
    person_gaze_pitch += person_gaze_pitch_adjustment

    return [person_gaze_yaw, person_gaze_pitch]

def getPersonLocation(person_id):
    """ Returns person's location as a list of x, y (right of robot -, left of robot +), and z coordinates in meters relative to spot between robot's feet """
    
    try:
        person_head_loc = memory.getData("PeoplePerception/Person/" + str(person_id) + "/PositionInRobotFrame")

    except RuntimeError:
        print "Couldn't get person's face location"
        return None

    else:
        person_x = person_head_loc[0]
        person_y = person_head_loc[1]
        person_z = person_head_loc[2]

        # print "The head is\t", person_x, "m away from me,\t", person_y, "m to the side, and\t", person_z, "m higher than my feet"

    return [person_x, person_y, person_z]

def personLookingAtObjects(person_gaze):

    # if person is looking lower than straight ahead (gaze pitch < 80 deg)
    if person_gaze[1] < deg2rad(80):
        return True

    return False

def getObjectLocation(person_gaze, person_location, debug = False):
    """ Returns object location relative to spot between robot's feet as a list of x, y, z in meters and yaw, pitch in radians """

    # unpack person gaze data (assuming person is looking at object)
    person_object_yaw = person_gaze[0]
    person_object_pitch = person_gaze[1]

    # unpack person location data relative to robot
    robot_person_x = person_location[0]
    robot_person_y = person_location[1]
    robot_person_z = person_location[2]

    # calculate x distance between robot and object
    person_object_x = robot_person_z * math.tan(person_object_pitch)
    # person_object_x = 0.8
    robot_object_x = robot_person_x - person_object_x
    # robot_object_x = 0.5

    # calculate y distance between robot and object (left of robot +, right of robot -)
    person_object_y = person_object_x * math.tan(person_object_yaw)
    robot_object_y = robot_person_y + person_object_y

    # calculate robot head yaw needed to gaze at object
    robot_object_yaw = math.atan(robot_object_y / robot_object_x)

    robot_object_z = 0
    robot_object_pitch = 0

    if debug:
        print "\tperson gaze:", rad2deg(person_gaze)
        print "\tperson loc:", person_location
        print "\tpers obj x", person_object_x
        print "\tpers obj y", person_object_y

    return [robot_object_x, robot_object_y, robot_object_z, robot_object_yaw, robot_object_pitch]

# set robot connection values
IP = 'bobby.local'
PORT = 9559

# set nao camera values
cam_num = 0
resolution = 2
colorspace = 13
fps = 10

# set game time limit
max_game_time = 15

# lists of object angles and confidences
object_angles = [-30, -10, -9, 15, 40]
object_angles = deg2rad(object_angles)
object_confidences = [0] * len(object_angles)

# set angle error in rad for determining which object(s) person is looking at
object_angle_error = math.pi / 12

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
memory = ALProxy("ALMemory")
gaze = ALProxy("ALGazeAnalysis")

# set brightness to default
camera.setCameraParameterToDefault("python_client", 0)

# subscribe to camera
video_client = camera.subscribeCamera("python_client", cam_num, resolution, colorspace, fps)

# stiffen whole body
motion.setStiffnesses("Body", 1.0)

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# tilt head up to look at person
motion.setAngles("HeadPitch", deg2rad(-10), 0.2)

# give robot some time to get to this angle before starting face tracker
time.sleep(0.5)

# set face tracker to use only head, not whole body
face_tracker.setWholeBodyOn(False)

# subscribe to gaze analysis
gaze.subscribe("_")

# set high tolerance for thinking that person is looking at robot so it's easy to get people IDs
gaze.setTolerance(1)

# start face tracker
face_tracker.startTracker()
print 'Face tracker successfully started!'

# wait a little to let robot find face
time.sleep(0.5)

# get people IDs
people_ids = getPeopleIDs()

# take ID of first person in list
person_id = people_ids[0]

person_gaze_pitch_adjustment = getPersonGazePitchAdjustment(person_id)

# finish talking
tts.say("Okay, let's play!")

# set timer
timeout = time.time() + max_game_time

# while 'q' is not pressed and time limit isn't reached
while (cv2.waitKey(1) & 0xFF != ord('q')) and (time.time() < timeout):

    try:
        # get person gaze data
        person_gaze = getPersonGaze(person_id, person_gaze_pitch_adjustment)

    # if gaze data can't be retrieved for that person ID anymore (e.g. if bot entirely loses track of person)
    except RuntimeError:
        print "Couldn't get gaze direction and head angles for that ID"
        
        # get new people IDs
        people_ids = getPeopleIDs()
        person_id = people_ids[0]

    # if gaze direction or head angles are empty lists (e.g. if person's gaze is too steep)
    except IndexError:
        print "Gaze data was empty list"

    else:
        # if person gaze is near the objects
        if personLookingAtObjects(person_gaze):

            # get person location data
            person_location = getPersonLocation(person_id)

            gaze_location = getObjectLocation(person_gaze, person_location)

            gaze_angle = gaze_location[3]
            
            # for count and angle of each object
            for i, object_angle in enumerate(object_angles):

                # if gaze angle is within object_angle_error of the object angle on either side
                if abs(object_angle - gaze_angle) <= object_angle_error:
                    
                    # add 1 to the confidence for that object
                    object_confidences[i] += 1

                    print "\t", rad2deg(object_angle),

            print

    # get image from nao
    nao_image = camera.getImageRemote(video_client)

    # display image with opencv
    images.showWithOpenCV(nao_image)

# print object_confidences
print object_confidences

# unsubscribe from gaze analysis
gaze.unsubscribe("_")

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
        print "Are you thinking of object " + str(i) + ', the one at ' + str(rad2deg(object_angles[i])) + " degrees?"
        motion.setAngles("HeadYaw", object_angles[i], 0.2)
        motion.setAngles("HeadPitch", deg2rad(15), 0.2)
        time.sleep(3)

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# remove stiffness
motion.setStiffnesses("Body", 0.0)