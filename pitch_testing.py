from __future__ import division
import cv2
import numpy
import time
import math
from naoqi import ALProxy
from naoqi import ALModule
from naoqi import ALBroker

# resize image
def resize(img, new_width = 500):
    if(len(img.shape) > 2):
        h, w, c = img.shape
    else:
        h, w = img.shape
    r = new_width / w
    dim = (new_width, int(h * r))
    img = cv2.resize(img, dim, interpolation = cv2.INTER_LINEAR)
    return img

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

def getPeopleIDs():

    # get list of IDs of people looking at robot
    people_ids = memory.getData("GazeAnalysis/PeopleLookingAtRobot")

    return people_ids

def getPersonGaze(person_id):
    """ Returns person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively. 
    Bases angles on person's eye gaze and head angles, and compensates for variable robot head position. """

    # if data exists
    try:
        # extract GazeDirection and HeadAngles values
        gaze_dir = memory.getData("PeoplePerception/Person/" + str(person_id) + "/GazeDirection")
        head_angles =  memory.getData("PeoplePerception/Person/" + str(person_id) + "/HeadAngles")

    # if getting gaze direction or head angles values caused an error
    except RuntimeError:
        print "Couldn't get gaze direction and head angles"

    # if able to retrieve gaze direction and head angles values
    else:

        # if gaze direction and head angles values hold valid data
        if len(gaze_dir) == 2 and len(head_angles) == 3:

            # print person ID
            # print "Person | ID", person_id
            
            # extract gaze direction and head angles data
            person_eye_yaw = gaze_dir[0]
            person_eye_pitch = gaze_dir[1]
            
            person_head_yaw = head_angles[0]
            person_head_pitch = head_angles[1]

            robot_head_yaw, robot_head_pitch = getRobotHeadAngles()
            
            # calculate overall gaze values (not in relation to robot's POV)
            person_gaze_yaw = -(person_eye_yaw + person_head_yaw) - robot_head_yaw # person's left is (-), person's right is (+)
            person_gaze_pitch = person_eye_pitch + person_head_pitch - robot_head_pitch + math.pi # all the way up is pi, all the way down is 0

            # return list of person's gaze yaw and pitch
            return [person_gaze_yaw, person_gaze_pitch]

        else:
            print "GazeDirection and HeadAngles values don't hold valid data"

def getRobotHeadAngles():

    # retrieve robot head angles
    robot_head_angles = motion.getAngles("Head", False)

    # unpack robot head angles
    robot_head_yaw = robot_head_angles[0] # left (+) and right (-)
    robot_head_pitch = -robot_head_angles[1] + math.pi / 2 # all the way up (pi) and all the way down (0), see http://doc.aldebaran.com/2-1/family/robots/joints_robot.html

    # return scaled robot head angles
    return [robot_head_yaw, robot_head_pitch]

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

    return [person_x, person_y, person_z]

def showWithOpenCV(nao_image, width = 500):

    # translate into one opencv can use
    img = (numpy.reshape(numpy.frombuffer(nao_image[6], dtype = '%iuint8' % nao_image[2]), (nao_image[1], nao_image[0], nao_image[2])))
    
    # resize image with opencv
    img = resize(img, width)

    # display marked-up image
    cv2.imshow('img', img)

# set robot connection values
IP = 'bobby.local'
PORT = 9559

# set nao camera values
cam_num = 0
resolution = 2
colorspace = 13
fps = 10

# set face-tracking time limit
wait = 15

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

# set face tracker to use only head, not whole body
face_tracker.setWholeBodyOn(False)

# start face tracker
face_tracker.startTracker()
print 'Face tracker successfully started!'

# subscribe to gaze analysis
gaze.subscribe("_")

pitch_sum = 0
height_sum = 0
loop_count = 0

# initialize timers
t0 = time.time()
t1 = 0

# while 'q' is not pressed and time limit isn't reached
while (cv2.waitKey(1) & 0xFF != ord('q')) and (t1 - t0 < wait):

    # get running time
    t1 = time.time()

    people_ids = getPeopleIDs()

    # if people_ids isn't "None" object
    if people_ids:

        # get ID of first person
        person_id = people_ids[0]

        # get person gaze data
        person_gaze = getPersonGaze(person_id)

        # if person_gaze isn't "None" object
        if person_gaze:

            loop_count += 1

            person_gaze_pitch = person_gaze[1]
            pitch_sum += person_gaze_pitch

            person_location = getPersonLocation(person_id)
            person_height = person_location[2]
            height_sum += person_height

    # get image from nao
    nao_image = camera.getImageRemote(video_client)

    # display image with opencv
    showWithOpenCV(nao_image)

# unsubscribe from gaze analysis
gaze.unsubscribe("_")

# stop face tracker
face_tracker.stopTracker()
print "Face tracker stopped."

# unsubscribe from camera
camera.unsubscribe(video_client)

cv2.destroyAllWindows()

pitch_avg = pitch_sum / loop_count
height_avg = height_sum / loop_count
print "Average Pitch:", rad2deg(pitch_avg)
print "Average Height:", round(height_avg, 2)

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# remove stiffness
motion.setStiffnesses("Body", 0.0)