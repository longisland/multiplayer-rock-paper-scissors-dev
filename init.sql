CREATE USER postgres WITH PASSWORD 'postgres';
ALTER USER postgres WITH SUPERUSER;
CREATE DATABASE rps_game;
GRANT ALL PRIVILEGES ON DATABASE rps_game TO postgres;