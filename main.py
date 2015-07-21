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

def gray(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray

def rad2deg(rad):
    if isinstance(rad, list):
        deg = []
        for angle in rad:
            deg.append(rad2deg(angle))
    else:
        deg = int(round(rad * 180 / math.pi))

    return deg

def getPeopleIDs():

    # get list of IDs of people looking at robot
    people_ids = memory.getData("GazeAnalysis/PeopleLookingAtRobot")

    return people_ids

def getPersonGaze(person_id):
    """ Returns person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively """

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
            print "Person | ID", person_id
            
            # extract gaze direction and head angles data
            person_eye_yaw = gaze_dir[0]
            person_eye_pitch = gaze_dir[1]
            
            person_head_yaw = head_angles[0]
            person_head_pitch = head_angles[1]

            robot_head_yaw, robot_head_pitch = getRobotHeadAngles()
            
            # calculate overall gaze values (not in relation to robot's POV)
            person_gaze_yaw = -(person_eye_yaw + person_head_yaw) - robot_head_yaw # person's left is (-), person's right is (+)
            person_gaze_pitch = person_eye_pitch + person_head_pitch - robot_head_pitch + math.pi # all the way up is pi, all the way down is 0

            print "\tRAW PITCH:", rad2deg(person_eye_pitch), rad2deg(person_head_pitch), rad2deg(person_eye_pitch + person_head_pitch)

            # # print overall gaze values
            # print '\tPerson gaze yaw:', person_gaze_yaw
            # print '\tPeron gaze pitch:', person_gaze_pitch

            # return tuple of gaze yaw and pitch
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
    """ Returns person's location as a list of x, y (right of robot -, left of robot +), and z coordinates in meters relative to the spot between the robot's feet """
    
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

    # if person is looking lower than straight ahead (gaze pitch < 90 deg)
    if person_gaze[1] < math.pi / 2:
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
        print "\trobot gaze:", rad2deg(robot_head_angles)
        print "\tpers obj x", person_object_x
        print "\tpers obj y", person_object_y

    return [robot_object_x, robot_object_y, robot_object_z, robot_object_yaw, robot_object_pitch]

def showWithOpenCV(nao_image, width = 500, detectFaces = False):

    # translate into one opencv can use
    img = (numpy.reshape(numpy.frombuffer(nao_image[6], dtype = '%iuint8' % nao_image[2]), (nao_image[1], nao_image[0], nao_image[2])))
    
    # resize image with opencv
    img = resize(img, width)

    # if detectFaces argument is set to True
    if detectFaces:

        # find faces
        faces = face_cascade.detectMultiScale(gray(img), scale_factor, min_neighbors)

        # for each face found
        for (x,y,w,h) in faces:
            # draw rectangle around face
            cv2.rectangle(img, (x,y), (x+w, y+h), (255, 0, 0), 1)
            
            # get crop of top half of face
            face = img[y:y+h/2, x:x+w]

            # detect eyes in that face
            eyes = eye_cascade.detectMultiScale(gray(face))
            
            # for each eye
            for (ex,ey,ew,eh) in eyes:
                # draw rectangle around eye
                cv2.rectangle(face, (ex, ey), (ex+ew, ey+eh), (0, 255, 0), 1)

    # display marked-up image
    cv2.imshow('img', img)

# get haar cascades for face and eye detection
face_cascade = cv2.CascadeClassifier('haar_cascades/haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('haar_cascades/haarcascade_eye.xml')

# set face detection tuning arguments
scale_factor = 1.1
min_neighbors = 6

# set robot connection values
IP = 'bobby.local'
PORT = 9559

# set nao camera values
cam_num = 0
resolution = 2
colorspace = 13
fps = 10

# set face-tracking time limit
wait = 180

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

# stand up in balanced stance
# posture.goToPosture("StandInit", 0.5)

# set face tracker to use whole body, not just heads
face_tracker.setWholeBodyOn(False)

# start face tracker
face_tracker.startTracker()
print 'Face tracker successfully started!'

# subscribe to gaze analysis
gaze.subscribe("_")

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

        # get person location data
        person_location = getPersonLocation(person_id)

        # if person_gaze isn't "None" object
        if person_gaze:

            # if person could be looking at an object
            if personLookingAtObjects(person_gaze):
                
                object_location = getObjectLocation(person_gaze, person_location, debug = True)
                print object_location

    # get image from nao
    nao_image = camera.getImageRemote(video_client)

    # display image with opencv
    showWithOpenCV(nao_image)

# unsubscribe from gaze analysis
gaze.unsubscribe("_")

# stop face tracker
face_tracker.stopTracker()

# unsubscribe from camera
camera.unsubscribe(video_client)

# sit down slowly
posture.goToPosture("Crouch", 0.2)

# remove stiffness
motion.setStiffnesses("Body", 0.0)
print "Face tracker stopped."

cv2.destroyAllWindows()