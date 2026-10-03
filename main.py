import numpy as np
import matplotlib.pyplot as plt

def simulate_fuel_dissolution(initial_mass_kg, acid_concentration_molar, temperature_celsius, total_time_hours):
    """
    Симулира разтварянето (dissolution) на отработено ядрено гориво (UO2) 
    в зависимост от температурата и времето.
    """
    # Времеви стъпки (в часове)
    time_steps = np.linspace(0, total_time_hours, 100)
    
    # Коефициент на реакцията, зависим от температурата (Arrhenius-like логика)
    # По-висока температура -> по-бързо разтваряне
    temp_factor = np.exp((temperature_celsius - 25) / 50) 
    
    # Скорост на разтваряне, зависима от концентрацията на киселината
    dissolution_rate = 0.05 * acid_concentration_molar * temp_factor
    
    # Симулация на оставащата маса на урановия оксид
    # Използваме експоненциален спад за процеса на разтваряне
    remaining_mass = initial_mass_kg * np.exp(-dissolution_rate * time_steps)
    
    # Образуване на разтворени актиниди и отпадъци в разтвора
    dissolved_uranium = initial_mass_kg - remaining_mass
    
    return time_steps, remaining_mass, dissolved_uranium

# Параметри за симулацията
initial_mass = 100.0  # кг отработено гориво в тестовата камера
acid_molarity = 4.0   # мол/л азотна киселина
temp = 60.0           # градуса по Целзий в пиро/химичния съд
hours = 10.0          # общо време на процеса

# Изпълнение на симулацията
time, mass_left, uranium_solution = simulate_fuel_dissolution(initial_mass, acid_molarity, temp, hours)

# Визуализация на резултатите (графика за журито)
plt.figure(figsize=(10, 5))
plt.plot(time, mass_left, label='Неразтворено гориво (UO2) [кг]', color='orange', linewidth=2.5)
plt.plot(time, uranium_solution, label='Извлечен/Разтворен уран в киселината [кг]', color='blue', linewidth=2.5)
plt.title('Симулация на химическо разтваряне (Dissolution) на ядрено гориво')
plt.xlabel('Време (часове)')
plt.ylabel('Маса (кг)')
plt.grid(True)
plt.legend()
plt.show()