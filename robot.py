import math
import time
import os

import numpy as np
# import speech_recognition as sr 
from naoqi import ALModule, ALProxy, ALBroker

count = 0
snd = None

def connect(address="bobby.local", port=9559, name="r", brokername="broker"):
	global broker
	broker = ALBroker("broker", "0.0.0.0", 0, address, 9559)
	global r
	r = Robot(name, address, 9559)

def robot():
	global r
	return r

def broker():
	global broker
	if not broker:
		broker = ALBroker("broker", "0.0.0.0", 0, "bobby.local", 9559)
	return broker

class Robot(ALModule):
	def __init__( self, strName, address = "bobby.local", port = 9559):
		ALModule.__init__( self, strName )
		self.outfile = None
		self.outfiles = [None]*(3)
		self.count = 99999999
		self.check = False

		# --- audio ---
		self.audio = ALProxy("ALAudioDevice", address, port)
		self.audio.setClientPreferences(self.getName(), 48000, [1,1,1,1], 0, 0)

		# --- speech recognition ---
		self.asr = ALProxy("ALSpeechRecognition", address, port)
		self.asr.setLanguage("English")

		self.yes_no_vocab = {
			"yes": ["yes", "ya", "sure", "definitely"],
			"no": ["no", "nope", "nah"]
		}

		# TODO: add unknown object names into this somehow
		# also add other names for objects dynamically??????
		self.object_vocab = {
			"digital_clock": ["digital clock", "blue clock", "black alarm clock"],
			"analog_clock": ["analog clock", "black clock", "black alarm clock"],
			"red_soccer_ball": ["red soccer ball", "red ball"],
			"basketball": ["basketball", "orange ball"],
			"football": ["football"],
			"yellow_book": ["yellow book"],
			"yellow_flashlight": ["yellow flashlight"],
			"blue_soccer_ball": ["blue soccer ball", "blue ball"],
			"apple": ["apple"],
			"black_mug": ["black mug"],
			"blue_book": ["blue book"],
			"blue_flashlight": ["blue flashlight"],
			"cardboard_box": ["cardboard box"],
			"pepper": ["pepper", "jalapeno"],
			"green_mug": ["green mug"],
			"polka_dot_box": ["polka dot box", "polka dotted box", "spotted box", "brown and white box"],
			"scissors": ["scissors"]
		}

		self.asr.setVocabulary([j for i in self.yes_no_vocab.values() for j in i], False)

		# --- text to speech ---
		self.tts = ALProxy("ALTextToSpeech", address, port)

		# --- memory ---
		self.mem = ALProxy("ALMemory", address, port)

		# --- robot movement ---
		self.motion = ALProxy("ALMotion", address, port)
		self.pose = ALProxy("ALRobotPosture", address, port)

		self.motion.stiffnessInterpolation("Body", 1.0, 1.0)
		self.pose.goToPosture("Crouch", 0.2)

		# --- face tracking ---
		self.track = ALProxy("ALFaceTracker", address, port)

		self.track.setWholeBodyOn(False)

		# --- gaze analysis ---
		self.gaze = ALProxy("ALGazeAnalysis", address, port)

		# --- camera ---
		self.cam = ALProxy("ALVideoDevice", address, port)

		# --- leds ---
		self.leds = ALProxy("ALLeds", address, port)

		self.colors = {
			"pink": 0x00FF00A2,
			"red": 0x00FF0000,
			"orange": 0x00FF7300,
			"yellow": 0x00FFFB00,
			"green": 0x000DFF00,
			"blue": 0x000D00FF,
			"purple": 0x009D00FF
		}

		# --- sound detection ---
		self.sound = ALProxy("ALSoundDetection", address, port)

		self.sound.setParameter("Sensibility", 0.95)

	def __del__(self):
		print "End Robot Class"

	def start(self):
		print "Starting Transcriber"
		self.audio.subscribe(self.getName())

	def stop(self):
		print "Stopping Transcriber"
		self.audio.unsubscribe(self.getName())
		if self.outfile != None:
			self.outfile.close()

	def processRemote(self, input_channels, input_samples, timestamp, input_buffer):
		print "listening"
		sound_data_interlaced = np.fromstring(str(input_buffer), dtype=np.int16)
		sound_data = np.reshape(sound_data_interlaced, (input_channels, input_samples), 'F')
		peak_value = np.max(sound_data)
		print "got peak value"
		if peak_value > 7500:
			print "Peak:", peak_value
			self.count = 30
		print "subtracting count"
		self.count -= 1
		if self.count == 0:
			print "STOP"*50
			self.check = True
		print "checked"
		if self.outfile == None:
			print "outfile was none"
			filename = "output.raw"
			self.outfile = open(filename, "wb")
		if self.outfile.closed:
			print "outfile was closed"
			filename = "output.raw"
			self.outfile = open(filename, "wb")
		print self.outfile
		sound_data[0].tofile(self.outfile)
		print "sent data to outfile"

	def say(self, text, block = True):
		"""
		Uses ALTextToSpeech to vocalize the given string.
		If "block" argument is False, makes call asynchronous.
		"""

		if block:
			self.tts.say(text)

		else:
			self.tts.post.say(text)

	def ask(self, question):
		"""
		Has the robot ask a question and returns the answer
		"""

		# If you're just trying to test voice detection, you can uncomment
		# the following 5 lines. Bobby will guess "yellow flashlight" and will prompt
		# you to correct him by saying "blue flashlight"

		# fake_answers = ["no", "yes", "yes", "yes", "no", "yes", "yes"]
		# global count
		# count += 1
		# print question
		# return fake_answers[count]

		self.say(question)
		#starts listening for an answer
		self.asr.subscribe("TEST_ASR")
		data = (None, 0)
		while not data[0]:
			data = self.mem.getData("WordRecognized")
		#stops listening after he hears yes or no
		self.asr.unsubscribe("TEST_ASR")

		print data

		for word in self.yes_no_vocab:
			for syn in self.yes_no_vocab[word]:
				if data[0] == syn:
					return word

	def ask_object(self):
		self.start()
		print "asking object"
		while True:
			if self.check:
				break
			time.sleep(1)
		self.stop()
		#uses sox to convert raw files to wav files
		os.system("sox -r 48000 -e signed -b 16 -c 1 output.raw speech.wav")

		r = sr.Recognizer()
		with sr.WavFile("speech.wav") as source:
			speech = r.record(source)
		try:
			possibilities = r.recognize(speech, True)
			print possibilities
			for possibility in possibilities:
				for word in self.object_vocab:
					for syn in self.object_vocab[word]:
						if possibility["text"] == syn:
							# global broker
							# broker.shutdown()
							# exit(0)
							return possibility
			raise LookupError
		except LookupError:
			self.say("I couldn't understand what you said. Please go to the computer and type the name of your object.")
			print "Type the name of your object exactly as you see here."
			print self.object_vocab.keys()
			# global broker
			# broker.shutdown()
			# exit(0)
			return raw_input("What object were you thinking of?")

	def wake(self):
		"""
		Turns stiffnesses on and goes to Crouch position
		"""

		self.motion.stiffnessInterpolation("Body", 1.0, 1.0)
		self.pose.goToPosture("Crouch", 0.2)

	def rest(self):
		"""
		Goes to Crouch position and turns robot stiffnesses off
		"""

		self.motion.rest()

	def turnHead(self, yaw = None, pitch = None, speed = 0.3):
		"""
		Turns robot head to the specified yaw and/or pitch in radians at the given speed.
		Yaw can range from 119.5 deg (left) to -119.5 deg (right) and pitch can range from 38.5 deg (up) to -29.5 deg (down).
		"""

		if not yaw is None:
			self.motion.setAngles("HeadYaw", yaw, speed)
		if not pitch is None:
			self.motion.setAngles("HeadPitch", pitch, speed)

	def colorEyes(self, color, fade_duration = 0.2):
		"""
		Fades eye LEDs to specified color over the given duration.
		"Color" argument should be either in hex format (e.g. 0x0063e6c0) or one of the following
		strings: pink, red, orange, yellow, green, blue, purple
		"""

		if color in self.colors:
			color = colors[color]

		self.leds.fadeRGB("FaceLeds", color, fade_duration)

	def getHeadAngles(self):
		"""
		Returns current robot head angles as a list of yaw, pitch.
		For yaw, from the robot's POV, left is positive and right is negative. For pitch, up is positive and down is negative.
		See http://doc.aldebaran.com/2-1/family/robots/joints_robot.html for info on the range of its yaw and pitch.
		"""

		robot_head_yaw, robot_head_pitch = self.motion.getAngles("Head", False)

		# return adjusted robot head angles
		return [robot_head_yaw, -robot_head_pitch]

	def resetEyes(self):
		"""
		Turns eye LEDs white.
		"""

		self.leds.on("FaceLeds")

	def waitForSound(self, time_limit = 7):
		"""
		Waits until either a sound is detected or until the given time limit expires.
		"""

		self.sound.subscribe("sound_detection_client")

		# give waiting a 7-second time limit
		timeout = time.time() + 7

		# check for new sounds every 0.2 seconds
		while (self.mem.getData("SoundDetected")[0] != 1) and (time.time() < timeout):
			time.sleep(0.2)

		self.sound.unsubscribe("sound_detection_client")

	def trackFace(self):
		"""
		Sets face tracker to just head and starts.
		"""

		# start face tracker
		self.track.setWholeBodyOn(False)
		self.track.startTracker()

	def stopTrackingFace(self):
		"""
		Stops face tracker.
		"""

		self.track.stopTracker()

	def subscribeGaze(self):
		"""
		Subscribes to gaze analysis module so that robot starts writing gaze data to memory.
		Also sets the highest tolerance for determining if people are looking at the robot because those people's IDs are the only ones stored.
		"""

		self.gaze.subscribe("_")
		self.gaze.setTolerance(1)

	def getPeopleIDs(self):
		"""
		Retrieves people IDs from robot memory. If list of IDs was empty, return None.
		"""

		people_ids = self.mem.getData("GazeAnalysis/PeopleLookingAtRobot")

		if people_ids is None or len(people_ids) == 0:
			return None

		return people_ids

	def getRawPersonGaze(self, person_id):
		"""
		Returns person's gaze as a list of yaw (left -, right +) and pitch (up pi, down 0) in radians, respectively.
		Bases gaze on both eye and head angles. Does not compensate for variable robot head position.
		"""

		try:
			# retrieve GazeDirection and HeadAngles values
			gaze_dir = self.mem.getData("PeoplePerception/Person/" + str(person_id) + "/GazeDirection")
			head_angles =  self.mem.getData("PeoplePerception/Person/" + str(person_id) + "/HeadAngles")

			# extract gaze direction and head angles data
			person_eye_yaw = gaze_dir[0]
			person_eye_pitch = gaze_dir[1]

			person_head_yaw = head_angles[0]
			person_head_pitch = head_angles[1]

		# RuntimeError: if gaze data can't be retrieved for that person ID anymore (e.g. if bot entirely loses track of person)
		# IndexError: if gaze direction or head angles are empty lists (e.g. if person's gaze is too steep)
		except (RuntimeError, IndexError):
			return None

		else:
			# combine eye and head gaze values
			person_gaze_yaw = -(person_eye_yaw + person_head_yaw) # person's left is (-), person's right is (+)
			person_gaze_pitch = person_eye_pitch + person_head_pitch + math.pi / 2 # all the way up is pi, all the way down is 0

			return [person_gaze_yaw, person_gaze_pitch]

	def getPersonLocation(self, person_id):
		"""
		Returns person's head location as a list of x, y (right of robot -, left of robot +), and z coordinates 
		in meters relative to spot between robot's feet.
		"""
		
		try:
			person_location = self.mem.getData("PeoplePerception/Person/" + str(person_id) + "/PositionInRobotFrame")

		except RuntimeError:
			# print "Couldn't get person's face location"
			person_location = None

		else:
			return person_location

	def unsubscribeGaze(self):
		"""
		Unsubscribes from gaze analysis module so the robot stops writing gaze data to its memory.
		"""

		self.gaze.unsubscribe("_")

#------------------------Main------------------------#

if __name__ == "__main__":

	print "#----------Audio Script----------#"

	connect("bobby.local")
	obj_name = r.ask_object()
	print obj_name

	broker.shutdown()
	exit(0)
