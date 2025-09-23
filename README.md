# Digital Chain of Custody

A Django-based web application that demonstrates the principles of a digital chain of custody.  
This project is developed as part of a Computer Security and Forensics course.

## Features
- Secure user authentication with role-based access.
- Case management dashboard for creating and managing cases.
- Evidence logging with metadata and cryptographic hash values.
- Tamper-evident custody transfer logs.
- Report generation for complete chain of custody records.
- Simulated evidence examples for academic and disciplinary cases.

## Tech Stack
- Django (Python web framework)
- SQLite (default database, can be swapped for others)
- HTML, CSS, JavaScript (frontend)

## Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/KenyanAudo03/digital_chain_of_custody.git
   cd digital_chain_of_custody
   ```

2. Create and activate a virtual env:
   ```bash
   python -m venv venv
    source venv/bin/activate  # On Windows use venv\Scripts\activate
    ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
    python manage.py runserver
    ```


## Licence
This project is for academic purposes only and not intended for production use.
