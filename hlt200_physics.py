import config as cfg
import math

class HLT200Physics:
    
    @staticmethod
    def calculate_leak_loss(p_start, p_end, minutes):
        """
        Formula 1: Leak Flow & Power Loss (Pressure Decay Test)
        Leak_Flow = (V * (P1 - P2)) / (t * Patm)
        """
        if minutes <= 0: return 0.0, 0.0
        
        leak_flow_m3_min = (cfg.TANK_VOLUME_M3 * (p_start - p_end)) / (minutes * cfg.ATMOSPHERIC_PRESSURE_BAR)
        
        # Leak % of Total Capacity
        leak_pct = leak_flow_m3_min / cfg.RATED_FLOW_M3_MIN
        
        # CORRECTED LOGIC: Uses Rated Power (energy needed to refill air)
        # instead of Actual Power (which is 0 when machine is OFF).
        kw_leak = leak_pct * cfg.RATED_POWER_KW
        
        return leak_flow_m3_min, kw_leak

    @staticmethod
    def calculate_over_pressure_waste(actual_pressure, actual_kw):
        """
        Formula 2: Over-Pressurization Loss
        Waste = ((P_act - P_opt) / P_opt) * kW
        """
        if actual_pressure <= cfg.OPTIMAL_PRESSURE_BAR:
            return 0.0
            
        waste_kw = ((actual_pressure - cfg.OPTIMAL_PRESSURE_BAR) / cfg.OPTIMAL_PRESSURE_BAR) * actual_kw
        return max(0.0, waste_kw)

    @staticmethod
    def calculate_idle_waste(actual_kw, machine_state):
        """
        Formula 3: Idle Running Loss
        If machine is UNLOADED (Run=ON, Load=OFF), 100% of energy is waste
        because the machine is consuming power but producing ZERO air.
        """
        if machine_state != "UNLOAD":
            return 0.0
        
        # Noise Filter: Ignore if power is practically zero (e.g. < 0.5 kW)
        if actual_kw < 0.5:
            return 0.0
            
        return actual_kw

    @staticmethod
    def calculate_expected_power(pressure, inlet_temp):
        """
        Formula 4 Support: Expected Physics Power (for Wear Detection)
        """
        base_kw = cfg.RATED_POWER_KW
        
        # Pressure Factor
        p_factor = 1.0 + ((pressure - cfg.OPTIMAL_PRESSURE_BAR) / cfg.OPTIMAL_PRESSURE_BAR)
        
        # Temp Factor
        t_factor = 1.0 + ((inlet_temp - cfg.DESIGN_INLET_TEMP_C) / 10 * cfg.TEMP_PENALTY_FACTOR)
        
        return base_kw * p_factor * t_factor

    @staticmethod
    def calculate_motor_efficiency_loss(voltage, current, pf):
        """
        Formula 5: Motor Inefficiency
        P_motor = sqrt(3) * V * I * PF
        """
        if pf >= cfg.HEALTHY_PF:
            return 0.0
            
        efficiency_drop = (cfg.HEALTHY_PF - pf) / cfg.HEALTHY_PF
        # Engineering Estimate: 20% of efficiency drop converts to real heat waste
        actual_power = (1.732 * voltage * current * pf) / 1000
        waste_kw = actual_power * efficiency_drop * 0.2 
        return waste_kw

    @staticmethod
    def calculate_hot_air_waste(inlet_temp, actual_kw):
        """
        Formula 6: Hot Inlet Air Loss
        Waste = ((T_act - T_design) / 10) * 0.04 * kW
        """
        if inlet_temp <= cfg.DESIGN_INLET_TEMP_C:
            return 0.0
            
        temp_diff = inlet_temp - cfg.DESIGN_INLET_TEMP_C
        waste_kw = (temp_diff / 10.0) * cfg.TEMP_PENALTY_FACTOR * actual_kw
        return max(0.0, waste_kw)