import numpy as np
import pandas as pd
import json
from datetime import datetime, timedelta
import math

class EnvironmentalDataSimulator:
    """
    Simulate realistic environmental data with time-series patterns
    for temperature, humidity, pH, and salinity.
    """
    
    def __init__(self, start_date, num_days, readings_per_day=24):
        """
        Initialize the simulator
        
        Parameters:
        - start_date: Starting date for data generation
        - num_days: Number of days to simulate
        - readings_per_day: Number of readings per day (default: 24 for hourly)
        """
        self.start_date = start_date
        self.num_days = num_days
        self.readings_per_day = readings_per_day
        self.total_readings = num_days * readings_per_day
        self.data = []
        
    def generate_timestamps(self):
        """Generate timestamps for the entire simulation period"""
        timestamps = []
        current_time = self.start_date
        hours_between_readings = 24 / self.readings_per_day
        
        for i in range(self.total_readings):
            timestamps.append(current_time)
            current_time += timedelta(hours=hours_between_readings)
        
        return timestamps
    
    def generate_temperature(self, timestamps):
        """
        Generate temperature data with daily and seasonal patterns
        Range: 15-35°C with daily fluctuations
        """
        temperatures = []
        
        for i, ts in enumerate(timestamps):
            # Seasonal pattern (sinusoidal over the year)
            day_of_year = ts.timetuple().tm_yday
            seasonal_component = 10 * math.sin(2 * math.pi * day_of_year / 365)
            
            # Daily pattern (cooler at night, warmer during day)
            hour_of_day = ts.hour + ts.minute / 60
            daily_component = 5 * math.sin(2 * math.pi * (hour_of_day - 6) / 24)
            
            # Base temperature
            base_temp = 25
            
            # Random noise
            noise = np.random.normal(0, 1)
            
            # Combine all components
            temp = base_temp + seasonal_component + daily_component + noise
            temperatures.append(round(temp, 2))
        
        return temperatures
    
    def generate_humidity(self, temperatures):
        """
        Generate humidity data inversely correlated with temperature
        Range: 40-90%
        """
        humidity_values = []
        
        for temp in temperatures:
            # Inverse relationship with temperature
            base_humidity = 90 - (temp - 15) * 1.5
            
            # Random variation
            noise = np.random.normal(0, 3)
            
            humidity = base_humidity + noise
            
            # Clamp between realistic values
            humidity = max(40, min(90, humidity))
            humidity_values.append(round(humidity, 2))
        
        return humidity_values
    
    def generate_pH(self):
        """
        Generate pH data with slight variations
        Range: 6.5-8.5 (typical for environmental water)
        """
        pH_values = []
        base_pH = 7.2
        
        for i in range(self.total_readings):
            # Slow drift over time
            drift = 0.3 * math.sin(2 * math.pi * i / (self.total_readings / 3))
            
            # Random variation
            noise = np.random.normal(0, 0.15)
            
            pH = base_pH + drift + noise
            
            # Clamp between realistic values
            pH = max(6.5, min(8.5, pH))
            pH_values.append(round(pH, 2))
        
        return pH_values
    
    def generate_salinity(self):
        """
        Generate salinity data (PSU - Practical Salinity Units)
        Range: 30-40 PSU (typical for seawater)
        """
        salinity_values = []
        base_salinity = 35
        
        for i in range(self.total_readings):
            # Gradual trend
            trend = 2 * math.sin(2 * math.pi * i / (self.total_readings / 2))
            
            # Random variation
            noise = np.random.normal(0, 0.5)
            
            salinity = base_salinity + trend + noise
            
            # Clamp between realistic values
            salinity = max(30, min(40, salinity))
            salinity_values.append(round(salinity, 2))
        
        return salinity_values
    
    def simulate(self):
        """Generate all environmental data"""
        print("Generating timestamps...")
        timestamps = self.generate_timestamps()
        
        print("Simulating temperature data...")
        temperatures = self.generate_temperature(timestamps)
        
        print("Simulating humidity data...")
        humidity = self.generate_humidity(temperatures)
        
        print("Simulating pH data...")
        pH = self.generate_pH()
        
        print("Simulating salinity data...")
        salinity = self.generate_salinity()
        
        # Create data records
        self.data = []
        for i in range(self.total_readings):
            record = {
                'timestamp': timestamps[i].strftime('%Y-%m-%d %H:%M:%S'),
                'temperature_celsius': temperatures[i],
                'humidity_percent': humidity[i],
                'pH': pH[i],
                'salinity_psu': salinity[i]
            }
            self.data.append(record)
        
        print(f"Generated {len(self.data)} data points")
        return self.data
    
    def export_to_csv(self, filename='environmental_data.csv'):
        """Export data to CSV format"""
        if not self.data:
            print("No data to export. Run simulate() first.")
            return
        
        df = pd.DataFrame(self.data)
        filepath = f'/mnt/user-data/outputs/{filename}'
        df.to_csv(filepath, index=False)
        print(f"Data exported to CSV: {filepath}")
        return filepath
    
    def export_to_json(self, filename='environmental_data.json'):
        """Export data to JSON format"""
        if not self.data:
            print("No data to export. Run simulate() first.")
            return
        
        filepath = f'/mnt/user-data/outputs/{filename}'
        
        # Create a structured JSON with metadata
        output = {
            'metadata': {
                'start_date': self.start_date.strftime('%Y-%m-%d'),
                'num_days': self.num_days,
                'readings_per_day': self.readings_per_day,
                'total_readings': self.total_readings,
                'parameters': ['temperature_celsius', 'humidity_percent', 'pH', 'salinity_psu']
            },
            'data': self.data
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"Data exported to JSON: {filepath}")
        return filepath
    
    def get_summary_statistics(self):
        """Get summary statistics of the generated data"""
        if not self.data:
            print("No data available. Run simulate() first.")
            return
        
        df = pd.DataFrame(self.data)
        df = df.drop('timestamp', axis=1)
        
        print("\n" + "="*60)
        print("SUMMARY STATISTICS")
        print("="*60)
        print(df.describe())
        print("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    print("="*60)
    print("ENVIRONMENTAL DATA SIMULATOR")
    print("="*60 + "\n")
    
    # Configuration
    start_date = datetime(2024, 1, 1)
    num_days = 30  # One month of data
    readings_per_day = 24  # Hourly readings
    
    # Create simulator
    simulator = EnvironmentalDataSimulator(
        start_date=start_date,
        num_days=num_days,
        readings_per_day=readings_per_day
    )
    
    # Generate data
    print(f"Configuration:")
    print(f"  Start Date: {start_date.strftime('%Y-%m-%d')}")
    print(f"  Duration: {num_days} days")
    print(f"  Readings per day: {readings_per_day}")
    print(f"  Total readings: {num_days * readings_per_day}\n")
    
    data = simulator.simulate()
    
    # Show sample data
    print("\nFirst 5 records:")
    print("-" * 60)
    for record in data[:5]:
        print(record)
    
    # Get statistics
    simulator.get_summary_statistics()
    
    # Export data
    print("Exporting data...")
    csv_file = simulator.export_to_csv()
    json_file = simulator.export_to_json()
    
    print("\n" + "="*60)
    print("SIMULATION COMPLETE!")
    print("="*60)
