import mysql.connector
from mysql.connector import Error
import logging
from config import Config

class DatabaseManager:
    """Veritabanı yönetim sınıfı"""
    
    def __init__(self):
        self.config = Config.DB_CONFIG
    
    def get_connection(self):
        """Güvenli veritabanı bağlantısı"""
        try:
            connection = mysql.connector.connect(**self.config)
            if connection.is_connected():
                logging.info("Veritabanına başarıyla bağlanıldı.")
                return connection
        except Error as e:
            logging.error(f"Veritabanı bağlantı hatası: {e}")
            return None
    
    def test_connection(self):
        """Veritabanı bağlantısını test et"""
        connection = self.get_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                connection.close()
                return True
            except Error as e:
                logging.error(f"Veritabanı test hatası: {e}")
                if connection:
                    connection.close()
        return False
    
    def get_categories_stats(self):
        """Kategori istatistiklerini getir"""
        connection = self.get_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM fetched_accounts 
                GROUP BY category 
                ORDER BY count DESC
            """)
            categories = cursor.fetchall()
            cursor.close()
            connection.close()
            return categories
        except Error as e:
            logging.error(f"Kategori istatistik hatası: {e}")
            if connection:
                connection.close()
            return []
    
    def get_total_stats(self):
        """Genel istatistikleri getir"""
        connection = self.get_connection()
        if not connection:
            return {'total_accounts': 0, 'unique_domains': 0, 'last_updated': 'Bilinmiyor'}
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Toplam hesap sayısı
            cursor.execute("SELECT COUNT(*) as total FROM fetched_accounts")
            total_accounts = cursor.fetchone()['total']
            
            # Benzersiz domain sayısı
            cursor.execute("SELECT COUNT(DISTINCT domain) as unique_domains FROM fetched_accounts")
            unique_domains = cursor.fetchone()['unique_domains']
            
            # Son güncelleme tarihi
            cursor.execute("SELECT MAX(fetch_date) as last_update FROM fetched_accounts")
            last_update_result = cursor.fetchone()
            last_updated = str(last_update_result['last_update']) if last_update_result['last_update'] else 'Bilinmiyor'
            
            cursor.close()
            connection.close()
            
            return {
                'total_accounts': total_accounts,
                'unique_domains': unique_domains,
                'last_updated': last_updated
            }
        except Error as e:
            logging.error(f"Genel istatistik hatası: {e}")
            if connection:
                connection.close()
            return {'total_accounts': 0, 'unique_domains': 0, 'last_updated': 'Bilinmiyor'}
    
    def search_accounts(self, query, page=1, limit=20, domain_filter='', region_filter='', source_filter=''):
        """Hesaplarda arama yap"""
        connection = self.get_connection()
        if not connection:
            return {'results': [], 'total': 0, 'error': 'Veritabanı bağlantısı başarısız'}
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Tablo yapısını öğren
            cursor.execute("DESCRIBE fetched_accounts")
            table_columns = cursor.fetchall()
            available_columns = [col['Field'] for col in table_columns]
            
            # Arama kolonlarını belirle
            search_columns = []
            if 'domain' in available_columns:
                search_columns.append('domain')
            
            username_columns = ['username', 'user', 'email', 'login', 'user_name', 'account']
            for col in username_columns:
                if col in available_columns and col not in search_columns:
                    search_columns.append(col)
                    break
            
            password_columns = ['password', 'pass', 'pwd', 'passwd', 'secret']
            for col in password_columns:
                if col in available_columns and col not in search_columns:
                    search_columns.append(col)
                    break
            
            # WHERE koşulları
            where_conditions = []
            params = []
            
            # Arama koşulu
            if search_columns:
                search_parts = []
                search_pattern = f"%{query}%"
                for col in search_columns:
                    search_parts.append(f"{col} LIKE %s")
                    params.append(search_pattern)
                where_conditions.append(f"({' OR '.join(search_parts)})")
            else:
                where_conditions.append("domain LIKE %s")
                params.append(f"%{query}%")
            
            # Filtreler
            if domain_filter:
                where_conditions.append("domain LIKE %s")
                params.append(f"%{domain_filter}%")
            if region_filter and 'region' in available_columns:
                where_conditions.append("region = %s")
                params.append(region_filter)
            if source_filter and 'source' in available_columns:
                where_conditions.append("source = %s")
                params.append(source_filter)
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Toplam sayı
            count_query = f"SELECT COUNT(*) as total FROM fetched_accounts {where_clause}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()['total']
            
            # Sayfalama
            total_pages = (total_count + limit - 1) // limit
            offset = (page - 1) * limit
            
            # Tarih kolonu
            date_column = 'fetch_date'
            if 'fetch_date' not in available_columns:
                for alt_date in ['created_at', 'date_added', 'timestamp', 'date', 'created']:
                    if alt_date in available_columns:
                        date_column = alt_date
                        break
                else:
                    date_column = available_columns[0]
            
            # Ana sorgu
            search_query = f"""
                SELECT * FROM fetched_accounts 
                {where_clause}
                ORDER BY {date_column} DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            
            cursor.execute(search_query, params)
            results = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            return {
                'results': results,
                'total': total_count,
                'pages': total_pages,
                'page': page,
                'available_columns': available_columns,
                'search_columns': search_columns
            }
            
        except Error as e:
            logging.error(f"Arama hatası: {e}")
            if connection:
                connection.close()
            return {'results': [], 'total': 0, 'error': str(e)}
    
    def get_table_structure(self):
        """Tablo yapısını getir - Debug için"""
        connection = self.get_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Tablo yapısını al
            cursor.execute("DESCRIBE fetched_accounts")
            columns = cursor.fetchall()
            
            # Örnek veri al
            cursor.execute("SELECT * FROM fetched_accounts LIMIT 1")
            sample_data = cursor.fetchone()
            
            # Toplam kayıt sayısı
            cursor.execute("SELECT COUNT(*) as total FROM fetched_accounts")
            total_count = cursor.fetchone()['total']
            
            # Domain örnekleri
            cursor.execute("SELECT DISTINCT domain FROM fetched_accounts LIMIT 10")
            sample_domains = [row['domain'] for row in cursor.fetchall()]
            
            cursor.close()
            connection.close()
            
            return {
                'columns': columns,
                'sample_data': sample_data,
                'total_count': total_count,
                'sample_domains': sample_domains,
                'columns_list': [col['Field'] for col in columns]
            }
            
        except Error as e:
            logging.error(f"Tablo yapısı hatası: {e}")
            if connection:
                connection.close()
            return None

# Global database instance
db = DatabaseManager()