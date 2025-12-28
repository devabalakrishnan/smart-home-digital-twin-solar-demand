import numpy as np
import gymnasium as gym
from stable_baselines3 import PPO

class MergedSolarHomeEnv(gym.Env):
    def __init__(self):
        super(MergedSolarHomeEnv, self).__init__()
        # Solar profile from your data
        self.solar_profile = [0.08, 0.08, 0.08, 0.08, 0.07, 0.07, 0.22, 1.20, 2.59, 3.38, 
                              4.03, 4.42, 5.09, 5.18, 4.86, 3.77, 2.57, 1.42, 0.43, 0.18, 
                              0.15, 0.13, 0.12, 0.09]
        
        self.current_hour = 0
        self.action_space = gym.spaces.Discrete(2) # 0: Grid-only, 1: Solar-Priority
        self.observation_space = gym.spaces.Box(low=0, high=24, shape=(1,), dtype=np.float32)

    def step(self, action):
        solar_gen = self.solar_profile[self.current_hour]
        
        # Simulated base demand for the hour
        base_demand = 1.5 
        
        # Agent Action: 1 means scheduling a high-load task (e.g., Washing Machine)
        additional_load = 2.0 if action == 1 else 0.0
        total_load = base_demand + additional_load
        
        # --- NET LOAD CALCULATION ---
        net_load = total_load - solar_gen
        
        # REWARD LOGIC: 
        # Positive if we cover the load with solar (net_load <= 0)
        # Negative if we pull from the grid (net_load > 0)
        if net_load <= 0:
            reward = 2.0  # Bonus for pure renewable usage
        else:
            reward = -net_load  # Penalty for grid reliance
        
        self.current_hour = (self.current_hour + 1) % 24
        obs = np.array([self.current_hour], dtype=np.float32)
        
        return obs, reward, False, False, {}

    def reset(self, seed=None):
        self.current_hour = 0
        return np.array([0], dtype=np.float32), {}
