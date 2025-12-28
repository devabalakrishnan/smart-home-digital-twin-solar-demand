import numpy as np
import gymnasium as gym
from stable_baselines3 import PPO

class SolarHomeEnv(gym.Env):
    def __init__(self):
        super(SolarHomeEnv, self).__init__()
        # Solar Data provided by user
        self.solar_profile = [0.08, 0.08, 0.08, 0.08, 0.07, 0.07, 0.22, 1.20, 2.59, 3.38, 
                              4.03, 4.42, 5.09, 5.18, 4.86, 3.77, 2.57, 1.42, 0.43, 0.18, 
                              0.15, 0.13, 0.12, 0.09]
        self.current_hour = 0
        self.action_space = gym.spaces.Discrete(2) # 0: Off, 1: On
        self.observation_space = gym.spaces.Box(low=0, high=24, shape=(1,), dtype=np.float32)

    def step(self, action):
        solar_gen = self.solar_profile[self.current_hour]
        load = 2.0 if action == 1 else 0.0 # 2kW appliance
        
        # Reward: High if using solar, low if pulling from grid
        net = load - solar_gen
        reward = 1.0 if net <= 0 else -net
        
        self.current_hour = (self.current_hour + 1) % 24
        return np.array([self.current_hour], dtype=np.float32), reward, False, False, {}

    def reset(self, seed=None):
        self.current_hour = 0
        return np.array([0], dtype=np.float32), {}