import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
from sklearn.linear_model import LinearRegression

# Define your filters here
MAKE = "Tesla"  # Set to None to see all makes
MODEL = "Model Y"    # Set to None to see all models for the selected make

def load_car_data(make=None, model=None):
    conn = sqlite3.connect('cars.db')
    
    # Build the SQL query with optional filters
    query = "SELECT * FROM cars WHERE 1=1"
    params = []
    if make:
        query += " AND make = ?"
        params.append(make)
    if model:
        query += " AND model = ?"
        params.append(model)
    
    df = pd.read_sql_query(query, conn, params=params)
    
    # Clean and convert data types with better error handling
    def clean_numeric(x):
        if pd.isna(x) or x == 'N/A':
            return None
        return ''.join(filter(str.isdigit, str(x)))
    
    # Clean price and mileage
    df['price'] = df['price'].apply(clean_numeric)
    df['mileage'] = df['mileage'].apply(clean_numeric)
    
    # Convert to numeric
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['mileage'] = pd.to_numeric(df['mileage'], errors='coerce')
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    
    # Drop rows where all key values are NaN
    df = df.dropna(subset=['price', 'mileage', 'year'], how='all')
    
    return df

def analyze_cars(make=None, model=None):
    df = load_car_data(make, model)
    
    if len(df) == 0:
        print("No data found in database!")
        return
    
    filter_text = ""
    if make:
        filter_text += f" for {make}"
        if model:
            filter_text += f" {model}"
    
    # Basic statistics
    print(f"\n=== Basic Statistics{filter_text} ===")
    print(f"Total cars: {len(df)}")
    print(f"Average price: {df['price'].mean():,.0f} kr")
    print(f"Median price: {df['price'].median():,.0f} kr")
    print(f"Average mileage: {df['mileage'].mean():,.0f} mil")
    print(f"Average year: {df['year'].mean():.1f}")
    
    # Only plot if we have data
    if len(df) > 0:
        # Price vs Mileage scatter plot with trendline
        plt.figure(figsize=(10, 6))
        sns.regplot(data=df.dropna(subset=['price', 'mileage']), 
                   x='mileage', y='price', 
                   scatter_kws={'alpha': 0.6},
                   line_kws={'color': 'red'})
        plt.title(f'Price vs Mileage{filter_text}')
        plt.xlabel('Mileage (mil)')
        plt.ylabel('Price (SEK)')
        plt.tight_layout()
        plt.savefig('price_vs_mileage.png', dpi=300)
        plt.show()
        
        # Average price by year
        yearly_data = df.groupby('year')['price'].mean().reset_index()
        yearly_data = yearly_data.dropna()
        if len(yearly_data) > 0:
            plt.figure(figsize=(10, 6))
            sns.lineplot(data=yearly_data, x='year', y='price')
            plt.title(f'Average Price by Year{filter_text}')
            plt.xlabel('Year')
            plt.ylabel('Average Price (SEK)')
            plt.tight_layout()
            plt.savefig('price_by_year.png', dpi=300)
            plt.show()
    
    # Location analysis
    print("\n=== Top Locations ===")
    location_counts = df['location'].replace('N/A', pd.NA).dropna().value_counts().head(10)
    print(location_counts)
    
    # Most expensive cars
    print("\n=== Top 5 Most Expensive Cars ===")
    expensive_cars = df.dropna(subset=['price']).nlargest(5, 'price')
    print(expensive_cars[['make', 'model', 'year', 'price', 'mileage', 'location']])
    
    # Newest cars
    print("\n=== Top 5 Newest Cars ===")
    newest_cars = df.dropna(subset=['year']).nlargest(5, 'year')
    print(newest_cars[['make', 'model', 'year', 'price', 'mileage', 'location']])

def predict_car_price(make=None, model=None):
    df = load_car_data(make, model)
    
    # Calculate age from year
    current_year = datetime.now().year
    df['age'] = current_year - df['year']
    
    # Clean data: Remove outliers and invalid entries
    df = df.dropna(subset=['price', 'mileage', 'age'])
    
    # Remove extreme outliers using IQR method
    def remove_outliers(df, column):
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        return df[~((df[column] < (Q1 - 1.5 * IQR)) | (df[column] > (Q3 + 1.5 * IQR)))]
    
    df = remove_outliers(df, 'price')
    df = remove_outliers(df, 'mileage')
    
    if len(df) < 10:
        print("Not enough data for reliable prediction")
        return
    
    # Prepare features
    X = df[['mileage', 'age']]
    y = df['price']
    
    # Train model
    model = LinearRegression()
    model.fit(X, y)
    
    # Print model coefficients
    print("\n=== Price Prediction Model ===")
    print(f"Base price (intercept): {model.intercept_:,.0f} kr")
    print(f"Price decrease per mil: {model.coef_[0]:,.0f} kr")
    print(f"Price decrease per year: {model.coef_[1]:,.0f} kr")
    print(f"R² score: {model.score(X, y):.3f}")
    
    # Interactive prediction
    print("\n=== Price Prediction Calculator ===")
    while True:
        try:
            mileage = float(input("Enter mileage (mil): "))
            age = float(input("Enter age (years): "))
            prediction_data = pd.DataFrame([[mileage, age]], columns=['mileage', 'age'])
            predicted_price = model.predict(prediction_data)[0]
            print(f"\nPredicted price: {predicted_price:,.0f} kr")
            
            # Calculate prediction interval (simplified)
            residuals = y - model.predict(X)
            std_dev = np.std(residuals)
            print(f"Price range: {(predicted_price - 2*std_dev):,.0f} kr to {(predicted_price + 2*std_dev):,.0f} kr")
            
            break
        except ValueError:
            print("Please enter valid numbers")
    
    # Create visualization
    plt.figure(figsize=(12, 5))
    
    # Price vs Mileage plot
    plt.subplot(1, 2, 1)
    plt.scatter(df['mileage'], df['price'], alpha=0.5)
    mileage_range = np.linspace(df['mileage'].min(), df['mileage'].max(), 100)
    avg_age = df['age'].mean()
    price_pred = model.predict(np.column_stack([mileage_range, [avg_age] * 100]))
    plt.plot(mileage_range, price_pred, 'r-', label='Prediction (avg age)')
    plt.xlabel('Mileage (mil)')
    plt.ylabel('Price (kr)')
    plt.title('Price vs Mileage')
    plt.legend()
    
    # Price vs Age plot
    plt.subplot(1, 2, 2)
    plt.scatter(df['age'], df['price'], alpha=0.5)
    age_range = np.linspace(df['age'].min(), df['age'].max(), 100)
    avg_mileage = df['mileage'].mean()
    price_pred = model.predict(np.column_stack([[avg_mileage] * 100, age_range]))
    plt.plot(age_range, price_pred, 'r-', label='Prediction (avg mileage)')
    plt.xlabel('Age (years)')
    plt.ylabel('Price (kr)')
    plt.title('Price vs Age')
    plt.legend()
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    predict_car_price(MAKE, MODEL)
