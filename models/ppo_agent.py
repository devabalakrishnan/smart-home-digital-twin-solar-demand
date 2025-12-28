import numpy as np
import gymnasium as gym

class MergedSolarHomeEnv(gym.Env):
    def __init__(self):
        super(MergedSolarHomeEnv, self).__init__()
        # 24-hour solar profile
        self.solar_profile = [0.08, 0.08, 0.08, 0.08, 0.07, 0.07, 0.22, 1.20, 2.59, 3.38, 
                              4.03, 4.42, 5.09, 5.18, 4.86, 3.77, 2.57, 1.42, 0.43, 0.18, 
                              0.15, 0.13, 0.12, 0.09]
        self.current_hour = 0
        self.action_space = gym.spaces.Discrete(2) # 0: Grid Only, 1: Solar Alignment
        self.observation_space = gym.spaces.Box(low=0, high=24, shape=(1,), dtype=np.float32)

    def step(self, action):
        solar_gen = self.solar_profile[self.current_hour]
        
        # Base demand from prediction
        base_demand = 1.2 
        
        # Action 1: Agent decides to run high-power appliances
        flexible_load = 2.5 if action == 1 else 0.0
        total_demand = base_demand + flexible_load
        
        # NET LOAD CALCULATION
        net_load = total_demand - solar_gen
        
        # SCHEDULING STRATEGY: 
        # High reward for consuming when solar is high (net_load <= 0)
        # Penalty for high grid consumption during no-solar hours
        if net_load <= 0:
            reward = 2.0  # Reward for 100% renewable usage
        else:
            reward = -net_load # Penalty proportional to grid pull
            
        self.current_hour = (self.current_hour + 1) % 24
        return np.array([self.current_hour], dtype=np.float32), reward, False, False, {}

    def reset(self, seed=None):
        self.current_hour = 0
        return np.array([0], dtype=np.float32), {}
