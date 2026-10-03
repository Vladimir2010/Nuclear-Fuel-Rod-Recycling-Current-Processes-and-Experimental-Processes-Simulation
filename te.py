import numpy as np
import matplotlib.pyplot as plt

def scientific_reprocessing_simulation():
    """
    Автоматична научна симулация на рециклиране и разтваряне на отработено ядрено гориво.
    Използва химична кинетика (Арениус) и масов баланс на елементите.
    """
    print("--- СТАРТИРАНЕ НА НАУЧЕН МОДЕЛ ЗА ЯДРЕНО РЕЦИКЛИРАНЕ ---")
    
    # 1. Начални параметри на отработеното гориво (в килограми за 1 тон гориво)
    initial_mass_total = 1000.0  # кг
    mass_uranium = 955.0         # кг (U-238 / U-235)
    mass_plutonium = 10.0        # кг (Pu-239)
    mass_fission_products = 35.0 # кг (Радиоактивни отпадъци / Cs, Sr, Ma)
    
    # 2. Условия на процеса (Автоматично зададени оптимални стойности за реактора)
    temperature_celsius = 75.0   # Оптимална температура на азотната киселина в съда
    temp_kelvin = temperature_celsius + 273.15
    activation_energy = 50000.0  # J/mol (Активираща енергия за разтваряне на UO2)
    R_gas = 8.314                # Универсална газова константа
    
    # 3. Изчисляване на скоростта на реакцията чрез закона на Арениус: k = A * exp(-E / (R*T))
    arrhenius_factor = 1e5       # предварителен множник
    reaction_rate_constant = arrhenius_factor * np.exp(-activation_energy / (R_gas * temp_kelvin))
    
    # Времеви стъпки на процеса (в часове от 0 до 10 часа)
    time_hours = np.linspace(0, 10, 100)
    
    # Маси във времето (Автоматично изчислени чрез кинетично уравнение от 1-ви ред)
    dissolution_progress = 1 - np.exp(-reaction_rate_constant * time_hours * 0.05)
    
    # Динамично разделяне на елементите в разтвора
    solved_uranium = mass_uranium * dissolution_progress
    solved_plutonium = mass_plutonium * dissolution_progress
    separated_waste = mass_fission_products * dissolution_progress
    
    # Извеждане на детайлен научен доклад в конзолата за журито
    print(f"\n[АВТОМАТИЧЕН ИЗЧИСЛИТЕЛЕН ДОКЛАД]")
    print(f"* Температура в реактора: {temperature_celsius} °C ({temp_kelvin} K)")
    print(f"* Първоначална маса на горивото: {initial_mass_total} кг")
    print(f"  - Уран в началото: {mass_uranium} кг")
    print(f"  - Плутоний в началото: {mass_plutonium} кг")
    print(f"  - Радиоактивни отпадъци: {mass_fission_products} кг")
    
    print(f"\n[РЕЗУЛТАТИ СЛЕД ПЪЛЕН ЦИКЪЛ НА РЕЦИКЛИРАНЕ (10 часа)]:")
    print(f"-> Успешно извлечен чист Уран: {solved_uranium[-1]:.2f} кг (Готов за ново ядрено гориво)")
    print(f"*  Успешно извлечен Плутоний: {solved_plutonium[-1]:.2f} кг (Готов за смесено MOX гориво)")
    print(f"*  Изолирани опасни отпадъци: {separated_waste[-1]:.2f} кг (За безопасно стъкло/остъкляване)")
    print(f"*  Обща ефективност на оползотворяване: {((solved_uranium[-1] + solved_plutonium[-1])/initial_mass_total)*100:.2f}%")

    # 4. Визуализация с научна графика
    plt.figure(figsize=(10, 6))
    plt.plot(time_hours, solved_uranium, label='Извлечен Уран (U) [кг]', color='blue', linewidth=2.5)
    plt.plot(time_hours, solved_plutonium, label='Извлечен Плутоний (Pu) [кг]', color='orange', linewidth=2.5)
    plt.plot(time_hours, separated_waste, label='Изолирани отпадъци (Fission Products) [кг]', color='red', linewidth=2.5)
    
    plt.title(f'Автоматична симулация на разтваряне (Dissolution) при {temperature_celsius} °C')
    plt.xlabel('Време на процеса (часове)')
    plt.ylabel('Маса на отделените елементи (кг)')
    plt.grid(True)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    scientific_reprocessing_simulation()