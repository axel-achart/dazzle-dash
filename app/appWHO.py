import pandas as pd
from sympy import print_rcode
df = pd.read_csv('C:/Users/Hippolyte_Geslain/Documents/LaPlateforme/B2/Repos/dazzle-dash/data/Life Expectancy Data.csv')
print(df.isnull().sum())
import seaborn as sns
import matplotlib.pyplot as plt
sns.heatmap(df.isnull(), cbar=False)
plt.show()
