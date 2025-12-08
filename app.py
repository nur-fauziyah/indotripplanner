import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from sqlalchemy import or_, create_engine
from sqlalchemy.orm import sessionmaker
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Create a Flask Instance
app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/db_wisata'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(10), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    level = db.Column(db.String(10), nullable=False)

    def __init__(self, username, password, location, age, level):
        self.username = username
        self.password = password
        self.location = location
        self.age = age
        self.level = level
    
    def get_id(self):
        return self.user_id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

class Wisata(db.Model):
    __tablename__ = 'tourism_with_id'

    place_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    place_name = db.Column(db.String(100), nullable = False)
    description = db.Column(db.String(5000), nullable = False)
    category = db.Column(db.String(20), nullable = False)
    city = db.Column(db.String(10), nullable = False)
    price = db.Column(db.String(10), nullable = False)
    rating = db.Column(db.String(10), nullable = False)
    image = db.Column(db.String(300), nullable = False)
    url = db.Column(db.String(1000), nullable = False)

    def __init__(self, place_name, description, category, city, price, rating, image, url):
        self.place_name = place_name
        self.description = description
        self.category = category
        self.city = city
        self.price = price
        self.rating = rating
        self.image = image
        self.url = url

class Favorite(db.Model):
    __tablename__ = 'tourism_favorite'
    favorite_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey('tourism_with_id.place_id'), nullable=False)

    user = db.relationship('User', backref=db.backref('favorites', lazy=True))
    place = db.relationship('Wisata', backref=db.backref('favorited_by', lazy=True))

    def __init__(self, user_id, place_id):
        self.user_id = user_id
        self.place_id = place_id

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create a route decorator
@app.route('/')
def index():
    return render_template("base.html")

@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        age = request.form.get('age')
        location = request.form.get('location')
        level = "user"
        
        # Cek apakah username sudah ada
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username sudah digunakan. Silakan pilih username lain.', 'danger')
        else:
            new_user = User(username=username, password=password, age=age, location=location, level=level)
                
            db.session.add(new_user)
            db.session.commit()
                
            flash('Registrasi berhasil. Silakan login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        next_page = request.args.get('next')
        
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            login_user(user)
            flash('Login Berhasil!', 'success')
            if user.level == 'admin':
                return redirect(next_page or url_for('admin_dashboard'))
            elif user.level == 'user':
                return redirect(next_page or url_for('dashboard'))
        else:
            flash('Login Gagal', 'danger')

    return render_template('login.html')

# Route for logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda Berhasil Logout!', 'success')
    return redirect(url_for('login'))

# Data wisata yang sudah di preprocessing
data_wisata = pd.read_csv('templates/data_wisata_preprocessed.csv')

# Inisialisasi TF-IDF Vectorizer
tfidf_vectorizer = TfidfVectorizer()
tfidf_matrix = tfidf_vectorizer.fit_transform(data_wisata['processed_description'])

# Hitung matriks cosine similarity
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# Fungsi untuk merekomendasikan tempat wisata
def recommend_places(user_id, threshold=0.03):
    try:
        engine = create_engine('mysql://root:@localhost/db_wisata')
        Session = sessionmaker(bind=engine)
        session = Session()

        data_favorite = session.query(Favorite).filter_by(user_id=user_id).all()
        session.close()

        user_favorites = [fav.place_id for fav in data_favorite]
        if not user_favorites:
            top_recommended_places = data_wisata.nlargest(10, 'rating')
            return top_recommended_places.to_dict(orient='records')
        
        # Misalkan user_favorites berisi place_id yang dimulai dari 1
        user_favorites_adjusted = [place_id - 1 for place_id in user_favorites]

        # Calculate the mean cosine similarity for each place in the user's favorites
        mean_similarity = cosine_sim[user_favorites_adjusted].mean(axis=0)

        # Get indices of top n places with highest mean similarity
        top_indices = mean_similarity.argsort()[::-1]

        # Menghapus tempat yang sudah menjadi favorit pengguna dari rekomendasi
        top_indices_filtered = [idx for idx in top_indices if (idx + 1) not in user_favorites]
        
        # Mengaplikasikan threshold pada cosine similarity
        top_indices_filtered = [idx for idx in top_indices_filtered if mean_similarity[idx] >= threshold]

        # Get recommended places
        recommended_places = data_wisata.iloc[top_indices_filtered].copy()

        # Hapus duplikat rekomendasi berdasarkan semua kolom
        # recommended_places = recommended_places.drop_duplicates(subset=['place_id'])

        return recommended_places.to_dict(orient='records')
    
    except Exception as e:
        print(f"Error in recommend_places: {e}")
        return []

# Route untuk mendapatkan rekomendasi
@app.route('/recommendations', methods=['GET'])
@login_required
def recommendations():
    if current_user.level != 'user':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))

    # Mendapatkan parameter dari query string
    user_id = int(request.args.get('user_id', current_user.user_id))
    recommendations = recommend_places(user_id)

    return render_template('recommendations.html', recommendations=recommendations, user_id=user_id)
    # return jsonify(recommendations)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.level != 'user':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    budaya = Wisata.query.filter_by(category='Budaya').order_by(Wisata.place_name.asc()).all()
    tamanhiburan = Wisata.query.filter_by(category='Taman Hiburan').order_by(Wisata.place_name.asc()).all()
    cagaralam = Wisata.query.filter_by(category='Cagar Alam').order_by(Wisata.place_name.asc()).all()
    bahari = Wisata.query.filter_by(category='Bahari').order_by(Wisata.place_name.asc()).all()
    pusatbelanja = Wisata.query.filter_by(category='Pusat Perbelanjaan').order_by(Wisata.place_name.asc()).all()
    ibadah = Wisata.query.filter_by(category='Tempat Ibadah').order_by(Wisata.place_name.asc()).all()
    return render_template('kategori.html', budaya=budaya, tamanhiburan=tamanhiburan, cagaralam=cagaralam, 
    bahari=bahari, pusatbelanja=pusatbelanja, ibadah=ibadah)

@app.route('/detail/<int:place_id>')
@login_required
def detail(place_id):
    if current_user.level != 'user':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    wisata = Wisata.query.get_or_404(place_id)
    return render_template('detail.html', wisata=wisata)

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if current_user.level != 'user':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    query = request.args.get('query', default='', type=str)
    results = []
    if query:
        # Menyesuaikan query untuk mencari berdasarkan nama, deskripsi, atau kategori
        results = Wisata.query.filter(
            or_(
                Wisata.place_name.ilike(f'%{query}%'),
                Wisata.description.ilike(f'%{query}%'),
                Wisata.category.ilike(f'%{query}%')
            )
        ).all()

    return render_template('search.html', results=results, query=query)

@app.route('/add_favorite/<int:place_id>', methods=['POST'])
@login_required
def add_favorite(place_id):
    favorite = Favorite.query.filter_by(user_id=current_user.user_id, place_id=place_id).first()
    if not favorite:
        new_favorite = Favorite(user_id=current_user.user_id, place_id=place_id)
        db.session.add(new_favorite)
        db.session.commit()
        flash('Destinasi ditambahkan ke favorit.', 'success')
    else:
        flash('Destinasi sudah ada di favorit.', 'info')
    return redirect(request.referrer)

@app.route('/remove_favorite/<int:place_id>', methods=['POST'])
@login_required
def remove_favorite(place_id):
    favorite = Favorite.query.filter_by(user_id=current_user.user_id, place_id=place_id).first()
    if favorite:
        place_name = favorite.place.place_name
        db.session.delete(favorite)
        db.session.commit()
        flash(f'Destinasi "{place_name}" dihapus dari favorit.', 'success')
    else:
        flash('Destinasi tidak ada di favorit.', 'info')
    return redirect(request.referrer)

@app.route('/favorites')
@login_required
def favorites():
    if current_user.level != 'user':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    
    favorites = Favorite.query.filter_by(user_id=current_user.user_id).all()

    return render_template('favorites.html', favorites=favorites)

@app.route('/admin_dashboard')
def admin_dashboard():
    if current_user.level != 'admin':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    total_places = Wisata.query.count()
    total_users = User.query.count()
    recent_activity = Wisata.query.order_by(Wisata.place_id.desc()).limit(5).all()

    return render_template('admin_dashboard.html', 
                           total_places=total_places, 
                           total_users=total_users,
                           recent_activity=recent_activity)

@app.route('/manage_wisata')
def manage_wisata():
    if current_user.level != 'admin':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    wisata = Wisata.query.order_by(Wisata.place_name.asc()).all()
    return render_template('admin_wisata.html', wisata=wisata)

@app.route('/add_wisata', methods=['GET', 'POST'])
def add_wisata():
    if request.method == 'POST':
        place_name = request.form['place_name']
        description = request.form['description']
        category = request.form['category']
        city = request.form['city']
        price = request.form['price']
        rating = request.form['rating']
        image = request.form['image']
        url = request.form['url']
        
        if not place_name or not description or not category or not city or not price or not rating or not image or not url:
            flash('Semua Field Harus Diisi', 'danger')
        else:
            new_wisata = Wisata(place_name=place_name, description=description, category=category, city=city, price=price, rating=rating, image=image, url=url)
            db.session.add(new_wisata)
            db.session.commit()
            flash('Wisata berhasil ditambahkan', 'success')
            return redirect(url_for('add_wisata'))
    
    return render_template('add_wisata.html')

@app.route('/edit/<int:place_id>', methods=['GET', 'POST'])
def edit_wisata(place_id):
    wisata = Wisata.query.get_or_404(place_id)
    if request.method == 'POST':
        wisata.place_name = request.form['place_name']
        wisata.description = request.form['description']
        wisata.city = request.form['city']
        wisata.rating = request.form['rating']
        wisata.price = request.form['price']
        wisata.image = request.form['image']
        wisata.url = request.form['url']
        wisata.category = request.form['category']

        try:
            db.session.commit()
            flash('Wisata berhasil di update', 'success')
            return redirect(url_for('manage_wisata', place_id=wisata.place_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')

    return render_template('edit_wisata.html', wisata=wisata)

@app.route('/delete/<int:place_id>', methods=['POST'])
def delete_wisata(place_id):
    wisata = Wisata.query.get_or_404(place_id)
    db.session.delete(wisata)
    db.session.commit()
    flash('Data wisata berhasil dihapus.', 'success')
    return redirect(url_for('manage_wisata'))

@app.route('/manage_user')
def manage_user():
    if current_user.level != 'admin':
        flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
        return redirect(url_for('login'))
    user = User.query.order_by(User.username.asc()).all()
    return render_template('admin_user.html', user=user)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        age = request.form.get('age')
        location = request.form.get('location')
        level = request.form.get('level')
        
        if not username or not password or not age or not location or not level:
            flash('Semua Field Harus Diisi', 'danger')
        else:
            new_user = User(username=username, password=password, age=age, location=location, level=level)
            db.session.add(new_user)
            db.session.commit()
            flash('Data User berhasil ditambahkan', 'success')
            return redirect(url_for('add_user'))
    
    return render_template('add_user.html')

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_userid(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Data user berhasil dihapus.', 'success')
    return redirect(url_for('manage_user'))

# Invalid URL
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# Internal Server Error
@app.errorhandler(500)
def page_not_found(e):
    return render_template("500.html"), 500

if __name__ == '__main__':
    app.run(debug=True)