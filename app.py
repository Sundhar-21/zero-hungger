from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
import os
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'a_real_secret_key_like_this_one_123')  # Ensure a strong key

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://ijisfoqbtgmuixzkzvzg.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlqaXNmb3FidGdtdWl4emt6dnpnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc3Mzc5ODAsImV4cCI6MjA3MzMxMzk4MH0.Vl4MChXgd_3XvD_PVvyYOv2wsb5AAESL7O9pP1zPFKc')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: Supabase credentials not set correctly! Exiting.")
    exit(1)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Test connection on startup
    test_response = supabase.table('users').select('*').limit(1).execute()
    print("Supabase client initialized and connection tested successfully.")
except Exception as e:
    print(f"ERROR: Failed to initialize Supabase client: {e}")
    exit(1)


def get_user_profile(user_id):
    """Fetch user profile from users table."""
    try:
        response = supabase.table('users').select('*').eq('user_id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error fetching profile for user_id {user_id}: {e}")
        return None


@app.route('/')
def home():
    """Homepage: Shows user profile if logged in."""
    try:
        user_auth = supabase.auth.get_user()
        if user_auth and user_auth.user:
            session['user_id'] = user_auth.user.id
            profile = get_user_profile(user_auth.user.id)
            if profile and not profile.get('name', '').strip():
                flash('Please complete your profile.', 'info')
                return redirect(url_for('complete_profile'))
            return render_template('index.html', user=profile)
        return render_template('index.html')
    except Exception as e:
        flash('Error loading home page.', 'error')
        print(f"Home error: {e}")
        return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup: Capture form data in session, create auth user and send confirmation email."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form.get('role', 'recipient').strip()
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')

        if not name or not city:  # Basic validation
            flash('Name and city are required!', 'error')
            return render_template('signup.html')

        session['pending_profile'] = {
            'role': role,
            'name': name,
            'phone': phone,
            'city': city,
            'address': address
        }
        session.modified = True  # Ensure session is saved
        print(f"DEBUG: Storing pending profile for {email}: {session['pending_profile']}")  # Debug

        try:
            auth_response = supabase.auth.sign_up({'email': email, 'password': password})
            if auth_response.user:
                flash('Signup successful! Please check your email to confirm your account.', 'success')
                return redirect(url_for('login'))
            else:
                session.pop('pending_profile', None)
                flash('Signup failed. Try again.', 'error')
        except Exception as e:
            session.pop('pending_profile', None)
            flash(f'Signup error: {str(e)}', 'error')
            print(f"Signup exception: {e}")

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login: After confirmation, insert user into users table using pending data if available."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            response = supabase.auth.sign_in_with_password({'email': email, 'password': password})
            if response.user:
                user_id = response.user.id
                session['user_id'] = user_id

                existing = supabase.table('users').select('*').eq('user_id', user_id).execute()
                if not existing.data:
                    pending = session.pop('pending_profile', None)
                    print(f"DEBUG: Retrieved pending for login email {email}: {pending}")  # Debug

                    if pending and pending.get('name'):  # Only use if name is present
                        role = pending.get('role', 'recipient')
                        name = pending.get('name', '')
                        phone = pending.get('phone', '')
                        city = pending.get('city', '')
                        address = pending.get('address', '')
                        print(f"DEBUG: Using pending data - Role: {role}, Name: {name}")  # Debug
                    else:
                        role = 'recipient'
                        name = ''
                        phone = ''
                        city = ''
                        address = ''
                        print(f"DEBUG: Using defaults - Role: {role}, Name: {name}")  # Debug

                    try:
                        insert_response = supabase.table('users').insert({
                            'user_id': user_id,
                            'email': email,
                            'role': role,
                            'name': name,
                            'phone': phone,
                            'city': city,
                            'address': address
                        }).execute()
                        print(f"DEBUG: Inserted profile for {user_id} with role {role}. Response: {insert_response}")  # Debug
                    except Exception as e:
                        flash(f'Failed to create profile: {str(e)}', 'error')
                        print(f"Insert exception: {e}")
                        return redirect(url_for('complete_profile'))  # Force profile completion

                profile = get_user_profile(user_id)
                if not profile.get('name', '').strip():
                    flash('Profile incomplete. Please update it.', 'info')
                    return redirect(url_for('complete_profile'))

                flash('Logged in successfully!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password.', 'error')
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            print(f"Login exception: {e}")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user."""
    try:
        supabase.auth.sign_out()
        session.pop('user_id', None)
        session.pop('pending_profile', None)
    except Exception as e:
        print(f"Logout error: {e}")
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))


@app.route('/complete_profile', methods=['GET', 'POST'])
def complete_profile():
    """Allow users to update their profile after login (optional, for changes or incomplete)."""
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            update_data = {
                'name': request.form['name'].strip(),
                'role': request.form['role'],
                'phone': request.form.get('phone', '').strip(),
                'city': request.form['city'].strip(),
                'address': request.form.get('address', '').strip()
            }
            supabase.table('users').update(update_data).eq('user_id', session['user_id']).execute()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            print(f"Update profile exception: {e}")

    profile = get_user_profile(session['user_id'])
    return render_template('signup.html', user=profile, is_update=True)


@app.route('/donate', methods=['GET', 'POST'])
def donate():
    """Upload donations if user is a donor."""
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    profile = get_user_profile(session['user_id'])
    if not profile or profile['role'].lower() != 'donor':
        flash('Only donors can upload donations! Your role is: ' + (profile['role'] if profile else 'None'), 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        try:
            quantity = float(request.form['quantity'])
            quality_rating = int(request.form['quality_rating'])
            description = request.form.get('description', '')

            # Handle image upload
            if 'image' not in request.files:
                flash('No image uploaded.', 'error')
                return render_template('upload_donation.html')

            image_file = request.files['image']
            if image_file.filename == '':
                flash('No image selected.', 'error')
                return render_template('upload_donation.html')

            # Upload image to Supabase Storage
            bucket_name = 'donation-images'
            file_path = f"donations/{session['user_id']}/{image_file.filename}"
            image_file.seek(0)  # Reset file pointer
            upload_response = supabase.storage.from_(bucket_name).upload(file_path, image_file.read(), {
                'content-type': image_file.content_type
            })
            print(f"DEBUG: Storage upload response: {upload_response}")

            # Verify upload success
            if not upload_response:
                flash('Failed to upload image to storage.', 'error')
                return render_template('upload_donation.html')

            image_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
            print(f"DEBUG: Generated image URL: {image_url}")

            # Verify image URL accessibility
            url_check = requests.head(image_url)
            if url_check.status_code != 200:
                flash(f'Image URL is not accessible (Status: {url_check.status_code}).', 'error')
                return render_template('upload_donation.html')

            # Insert donation into database
            insert_data = {
                'user_id': session['user_id'],
                'quantity': quantity,
                'quality_rating': quality_rating,
                'description': description,
                'image_url': image_url
            }
            insert_response = supabase.table('donations').insert(insert_data).execute()
            print(f"DEBUG: Donation insert response: {insert_response.data}, Count: {insert_response.count}")
            flash('Donation uploaded successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: Donation upload exception: {error_msg}")
            if 'PGRST204' in error_msg or 'column' in error_msg.lower():
                flash(f'Database schema error: {error_msg}. Ensure all columns exist in the donations table.', 'error')
            elif 'row-level security' in error_msg.lower():
                flash(f'RLS error: {error_msg}. Check your RLS policies.', 'error')
            else:
                flash(f'Error uploading donation: {error_msg}', 'error')
            return render_template('upload_donation.html')

    return render_template('upload_donation.html')


@app.route('/view_donations')
def view_donations():
    """View donations for recipients/NGOs."""
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    profile = get_user_profile(session['user_id'])
    if not profile or profile['role'].lower() not in ['recipient', 'ngo']:
        flash('Only recipients and NGOs can view donations. Your role: ' + (profile['role'] if profile else 'None'), 'error')
        return redirect(url_for('home'))

    try:
        response = supabase.table('donations').select(
            '*, users!donations_user_id_fkey(name)'
        ).execute()
        donations = response.data
        return render_template('view_donations.html', donations=donations, user=profile)
    except Exception as e:
        flash(f'Error fetching donations: {str(e)}', 'error')
        return redirect(url_for('home'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)