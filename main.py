from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel
import uvicorn
import requests
from bs4 import BeautifulSoup
import json
from typing import List, Optional

app = FastAPI()

# Initialize OpenAI client
client = OpenAI()

class Website:
    """A utility class to represent a Website that have been scraped"""
    
    def __init__(self, url):
        self.url = url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        self.body = response.content
        soup = BeautifulSoup(self.body, 'html.parser')
        self.title = soup.title.string if soup.title else "No title found"
        if soup.body:
            for irrelevant in soup.body(["script", "style", "img", "input"]):
                irrelevant.decompose()
            self.text = soup.body.get_text(separator="\n", strip=True)
        else:
            self.text = ""
        links = [link.get('href') for link in soup.find_all('a')]
        self.links = [link for link in links if link]

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"

class CoverLetterRequest(BaseModel):
    applicant_name: str
    portfolio_url: str
    job_title: str
    company_name: str
    key_skills: List[str]
    tone: Optional[str] = "professional"  # Can be "professional" or "confident"

def get_links(url: str) -> dict:
    """Analyze webpage links and return relevant ones"""
    website = Website(url)
    
    link_system_prompt = """You are provided with a list of links found on a personal webpage. 
    You are able to decide which of the links would be most relevant to include in a cover letter
    such as links to technologies, projects, contact sections, and skills."""
    
    link_system_prompt += """
    You should respond in JSON as in this example:
    {
        "links": [
            {"type": "projects", "url": "https://portfolio.com/projects"},
            {"type": "skills", "url": "https://portfolio.com/skills"}
        ]
    }
    """
    
    user_prompt = f"Here is the list of links on the website of {url} - "
    user_prompt += """please decide which of these are relevant sections to reference in a cover letter, 
    respond with the full https URL in JSON format. Focus on projects, skills, and experience sections.\n"""
    user_prompt += "Links (some might be relative links):\n"
    user_prompt += "\n".join(website.links)

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def get_all_details(url: str) -> str:
    """Get content from main page and all relevant linked pages"""
    result = "Portfolio content:\n"
    result += Website(url).get_contents()
    links = get_links(url)
    
    for link in links["links"]:
        result += f"\n\n{link['type']}\n"
        try:
            result += Website(link["url"]).get_contents()
        except:
            continue
            
    return result[:5000]  # Truncate to avoid token limits

@app.get("/")
def welcome():
    return {"message": "Welcome to the Cover Letter Generator API"}

@app.post("/generate-cover-letter")
def generate_cover_letter(request: CoverLetterRequest):
    # Set system prompt based on tone
    if request.tone == "confident":
        system_prompt = """You are an assistant that creates confident, compelling cover letters. 
        Analyze the portfolio content and create a cover letter that emphasizes achievements and potential impact. 
        Keep the tone confident but not arrogant. Focus on specific projects and skills that match the job requirements. 
        Format the response in markdown. The letter should be one page in length."""
    else:
        system_prompt = """You are an assistant that creates professional, well-structured cover letters. 
        Analyze the portfolio content and create a formal cover letter that emphasizes relevant experience and skills. 
        Keep the tone professional and courteous. Focus on specific projects and skills that match the job requirements. 
        Format the response in markdown. The letter should be one page in length."""

    # Get portfolio content
    portfolio_content = get_all_details(request.portfolio_url)

    # Create user prompt
    user_prompt = f"""Create a cover letter for {request.applicant_name} applying for the position of {request.job_title} 
    at {request.company_name}. The applicant has the following key skills: {', '.join(request.key_skills)}.
    
    Here is the content from their portfolio website to reference:
    
    {portfolio_content}
    
    Create a cover letter that specifically connects their portfolio projects and skills to the job requirements."""

    # Generate cover letter
    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    
    return {"cover_letter": response.choices[0].message.content}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)