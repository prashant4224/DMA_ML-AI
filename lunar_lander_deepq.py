import gym
import pandas as pd
import numpy as np
from collections import deque
import random
import copy

import keras
from keras.models import Sequential, Model
from keras.layers import Conv2D
from keras.layers.core import Dense, Dropout, Flatten

from my_util import makeGraph

# if first frame of episode, fills stack with new_frame
# if not first frame, adds new_frame to existing stack
def stackFrames(stacked_frames, frame, new_episode):
	return_stack = stacked_frames
	return_state = None

	# if first frame of the episode, fill the stack with frame
	if new_episode:
		for _ in range(stack_size):
			return_stack.append(frame)
	# otherwise, add frame to stack once
	else:
		return_stack.append(frame)

	# build our return state, and return it with the stack
	return_state = np.stack(return_stack, axis=1)
	return return_state, return_stack

# generate a new action based on either random or prediction
def predictAction(model, decay_step):
	# random number to compare to epsilon
	tradeoff = np.random.random()
	# update epsilon based on decay_step
	epsilon = max_epsilon \
				   + (min_epsilon - max_epsilon) \
				   * np.exp(-decay_rate * decay_step)

	if epsilon > tradeoff:
		# in early training, generate mostly random moves
		choice = random.randint(1, len(action_codes)) - 1
	else:
		# as epsilon decays, more moves are based on predicted rewards
		# first, reshape frame_stack to model's desired input shape
		feats = np.array(frame_stack).reshape(1, *state_space, 1)
		# generate predictions based on frame_stack features
		predicts = model.predict(feats)
		# generate a choice (index) based on predicted rewards
		choice = np.argmax(predicts)

	# return the action code associated with choice made
	return action_codes[choice]

# generates a random sampling of the list passed in
def sampleMemory(buffered_list, batch_size):
	buffer_size = len(buffered_list)
	# generates a list of random indices to pick
	index = np.random.choice(np.arange(buffer_size),
							 size=batch_size,
							 replace=False)
	return [buffered_list[i] for i in index]

# defines our keras model for Deep-Q training
def getModel():
	model = Sequential()
	model.add(Conv2D(100, (1, 8),
					 input_shape=(*state_space, 1)))
	model.add(Conv2D(75, (1, 8)))
	model.add(Flatten())
	model.add(Dense(50, activation="relu"))
	model.add(Dense(25, activation="relu"))
	model.add(Dense(10, activation="relu"))
	model.add(Dense(action_space, activation="softmax"))
	opt = keras.optimizers.Adam(lr=learning_rate,
								beta_1=min_epsilon,
								beta_2=max_epsilon,
								decay=decay_rate)
	model.compile(optimizer=opt,
				  loss="categorical_crossentropy")
	return model

# main code
# start by building gym environment
env = gym.make("LunarLander-v2")

# lots of constants
success = False
stack_size = 15
total_episodes = 10000
max_steps = 250
batch_size = 256
learning_rate = 0.00025
gamma = 0.618
max_epsilon = 1.0
min_epsilon = 0.01
decay_rate = 0.00001
decay_step = 0

# figure out size of state and action spaces
state_space = (8, stack_size)
action_space = env.action_space.n
# generate an array of all possible action codes (1-hot encoding)
action_codes = np.identity(action_space, dtype=np.int).tolist()

# generating a frame stack filled with empty (zeros) images
blank_frames = [np.zeros((110, 84), dtype=np.int) \
					   for i in range(stack_size)]
frame_stack = deque(blank_frames, maxlen = stack_size)

# build model, and create memory collection
model = getModel()
memory = deque(maxlen=250000)
score_list = []
for episode in range(total_episodes):
	# reset environment, initialize variables
	state = env.reset()
	score = 0.0
	state, frame_stack = stackFrames(frame_stack, state, True)

	# iterate through steps in the episode
	for step in range(max_steps):
		# render, so we can watch
#		env.render()
		# increment decay_step to update epsilon
		decay_step += 1

		# generate an action
		action = np.argmax(predictAction(model, decay_step))

		# apply action to step the environment
		obs, reward, done, _ = env.step(action)

		# add received reward to episode score
		score += reward

		# if the last frame of the episode, flag success,
		# and append empty frame to frame_stack
		if done == True:
			if reward >= 200.0:
				success = True
			obs = np.zeros((8,))
			obs, frame_stack = stackFrames(frame_stack, obs, False)
			break
		# otherwise, simply add current frame to frame_stack
		else:
			obs, frame_stack = stackFrames(frame_stack, obs, False)

		# either way, compile memory and add it to collection
		memory.append((state, action, reward))
		# set state for next iteration
		state = obs

	score_list.append(score)

	if success:
		break

	# after each episode, do training if more than 100 memories
	if len(memory) > 500:
		# first, separate memory into component data items
		batch = sampleMemory(memory, batch_size)
		states = np.array([item[0] for item in batch])
		states = states.reshape(batch_size, *state_space, 1)
		next_states = copy.deepcopy(states)
		actions = [item[1] for item in batch]
		rewards = [item[2] for item in batch]

		# generate expected rewards for selected states
		predicts = model.predict(next_states)
		# 
		targets = [gamma * np.max(item) for item in predicts]
		targets = [targets[i] + rewards[i] for i in range(len(targets))]
		target_fit = [item for item in model.predict(states)]

		# populate labels with expected outcomes
		for i in range(len(target_fit)):
			target_fit[i][actions[i]] = targets[i]

		# format features and labels for training
		feats = np.array(states).reshape(-1, *state_space, 1)
		lbls = np.array(target_fit).reshape(-1, action_space)
		# train the model on selected batch
		model.train_on_batch(x=feats, y=lbls)

	print("Score for episode {}: {}".format(episode, score))

makeGraph(score_list)

if success:
	print("We win!")
else:
	print("We lose...")