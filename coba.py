from sqlalchemy import create_engine, text

# Ganti `db_wisata` dengan nama database yang sesuai
engine = create_engine('mysql+pymysql://root:@localhost/db_wisata')

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print(result.scalar())
except Exception as e:
    print(f"Error connecting to database: {str(e)}")