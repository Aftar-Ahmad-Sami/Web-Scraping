from flask import Flask, render_template_string, request
import pandas as pd

app = Flask(__name__)

@app.route('/')
def home():
    return '''
        <h1>BDNews24 Headlines</h1>
        <form action="/refresh">
            <input type="submit" value="Refresh Headlines">
        </form>
        <br>
        <a href="/headlines">View Latest Headlines</a>
    '''

@app.route('/refresh')
def refresh():
    import subprocess
    
    # Run the scraper script again to get fresh data 
    subprocess.run(["python", "scrapper.py"])
    
    return '''
        <p>Headlines refreshed!</p>
        <a href="/">Go back</a>'
    '''

@app.route('/headlines')
def headlines():
    
   try:
       # Load scraped data from CSV file 
       df = pd.read_csv("bdnews24_headlines.csv")
       
       if df.empty:
           raise ValueError("No data available")

       articles = df.to_dict(orient='records')

       return render_template_string("""
           <h1>Latest BDNews24 Headlines</h1>

               {% if not articles %}
                   <p>No headlines found.</p>
               {% else %}
                   <ul>
                       {% for article in articles %}
                           <li><h1><a href="{{ article.link }}" target="_blank">{{ article.title }}</a></h1></li>
                       {% endfor %}
                   </ul>
               {% endif %}""",
          articles=articles)
          
   except (pd.errors.EmptyDataError, ValueError) as e:
      return f'''
          <p>No headlines available at the moment. Please try refreshing later.</p>'
          Error details: {e}
          </br><a href="/">Go back</a>'
      '''

if __name__ == '__main__':
     app.run(debug=True)
