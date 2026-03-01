# -*- coding: utf-8 -*-
# @Time    : 2024/11/14 20:32
# @Author  : zlh
# @File    : db.py
import MySQLdb

# global variables
db = MySQLdb.connect(
    host='localhost',
    user='root',
    passwd='12345678',
    db='ai240708'
)
cursor = db.cursor()

def db_user_login(name, password):
    print('db_user_login connection successful')
    sql = "SELECT * FROM Tbl_user WHERE user_name='{}' AND user_pwd = MD5('{}')".format(name, password)
    print(sql)
    try:
        i = cursor.execute(sql)
        db.commit()
        print('i:', i)
        if i > 0:
            results = cursor.fetchall()
            print(len(results))
            for row in results:
                print(row)
            print(row[0])
            return row[0]
        else:
            return 0
    except:
        print(db.error())
        db.rollback()
        return 0

def db_user_Register(name, passwd, Phone=None):
    print('db_user_Register connection successful')
    sql = "INSERT INTO Tbl_user(user_name, user_pwd, user_status) VALUES(%s, MD5(%s), 1)"
    cursor.execute(sql, (name, passwd))
    print('Insertion completed')
    db.commit()

def db_photo_insert(photo_name, photo_address, photo_time, user_id):
    print('db_photo_insert connection')
    sql = "INSERT INTO tbl_photo(photo_name, photo_address, photo_time, user_id, photo_status) VALUES('{}', '{}', '{}', {}, 1);".format(
        photo_name, photo_address, photo_time, user_id)
    print(sql)

    try:
        cursor.execute(sql)
        db.commit()
        print('Insertion completed')
        results = cursor.fetchall()
        if results:
            return 1
        else:
            return 0
    except:
        print(db.error)
        db.rollback()
        return 0

def db_photo_select(pagenow, pagecount, user_id):
    start = (pagenow - 1) * pagecount
    sql = "SELECT * FROM tbl_photo WHERE user_id = %s ORDER BY photo_id DESC LIMIT %s, %s;"
    params = (user_id, start, pagecount)
    print('db_photo_select connection successful')
    try:
        i = cursor.execute(sql, params)
        db.commit()
        results = cursor.fetchall()
        print('Query result:', results)
        if i > 0:
            return results
        else:
            return 0
    except:
        print(db.error)
        db.rollback()
        return 0

def update_password(user_pwd, user_id):
    print('update_password connection successful')
    sql = "UPDATE Tbl_user SET user_pwd = MD5(%s) WHERE user_id = %s;"
    try:
        cursor.execute(sql, (user_pwd, user_id))
        print(sql)
        db.commit()
        print('Update completed')
        results = cursor.fetchall()
        if results:
            return 1
        else:
            return 0
    except:
        print(db.error)
        db.rollback()
        return 0

def update_avatars(user_avtar, user_id):
    print('Connection successful')
    sql = "UPDATE Tbl_user SET user_avatar = '{}' WHERE user_id = {};".format(user_avtar, user_id)
    print(sql)
    try:
        cursor.execute(sql)
        db.commit()
        print('update_avatars update completed')
        results = cursor.fetchall()
        if results:
            return 1
        else:
            return 0
    except:
        print(db.error)
        db.rollback()
        return 0

def db_headpicture(user_id):
    print('db_headpicture connection successful')
    sql = "SELECT user_avatar FROM tbl_user WHERE user_id = {};".format(user_id)
    print(sql)
    try:
        cursor.execute(sql)
        result = cursor.fetchone()
        print("Query result:", result)
        if result:
            return result[0]
        else:
            print("No avatar found for user ID {}".format(user_id))
            return None
    except:
        print(db.error)
        db.rollback()
        return user_id

def db_VideoInterface(user_id, pagenow, pagecount):
    try:
        print('db_VideoInterface connection')
        start = (pagenow - 1) * pagecount
        sql = "SELECT * FROM tbl_video WHERE user_id = %s ORDER BY video_id DESC LIMIT %s, %s;"
        i = cursor.execute(sql, (user_id, start, pagecount))
        print(sql)
        db.commit()
        print('Query completed')
        results = cursor.fetchall()
        if i > 0:
            return results
        else:
            return 0
    except MySQLdb.Error as e:
        print(f"MySQL Error [{e.args[0]}]: {e.args[1]}")
        db.rollback()
        return 0

def db_video_save(user_id, video_name, video_address, video_interface):
    try:
        print('db_VideoInterface connection')
        sql = "INSERT INTO tbl_video(video_name, video_address, video_interface, user_id, video_status) VALUES('{}', '{}', '{}', {}, 1);".format(
            video_name, video_address, video_interface, user_id)
        cursor.execute(sql)
        print(sql)
        db.commit()
        print('Insertion completed')
        return 1
    except MySQLdb.Error as e:
        print(f"MySQL Error [{e.args[0]}]: {e.args[1]}")
        db.rollback()
        return 0

def db_search_pages(user_id):
    try:
        print('db_search_pages')
        sql = 'SELECT count(*) FROM tbl_photo WHERE user_id = {}'.format(user_id)
        i = cursor.execute(sql)
        db.commit()
        result = cursor.fetchall()
        if i > 0:
            print('Total photos found:', result)
            return result[0]
        else:
            return 0
    except MySQLdb.Error as e:
        print(f"MySQL Error [{e.args[0]}]: {e.args[1]}")
        db.rollback()
        return 0

def db_search_pages_video(user_id):
    try:
        print('db_search_pages')
        sql = 'SELECT count(*) FROM tbl_video WHERE user_id = {}'.format(user_id)
        i = cursor.execute(sql)
        db.commit()
        result = cursor.fetchall()
        if i > 0:
            print('Total videos found:', result)
            return result[0]
        else:
            return 0
    except MySQLdb.Error as e:
        print(f"MySQL Error [{e.args[0]}]: {e.args[1]}")
        db.rollback()
        return 0

def db_video_delete(user_id, video_path):
    """
    Deletes the video record for the specified user ID and video path
    :param user_id: User ID (integer)
    :param video_path: Video file path (string, must match stored path in database)
    :return: Boolean indicating success status of deletion
    """
    try:
        sql = "DELETE FROM tbl_video WHERE user_id = %s AND video_address = %s"
        cursor.execute(sql, (user_id, video_path))
        db.commit()
        if cursor.rowcount > 0:
            print(f"Successfully deleted video record: user_id={user_id}, path={video_path}")
            return True
        else:
            print(f"No matching video record found: user_id={user_id}, path={video_path}")
            return False
    except MySQLdb.Error as e:
        print(f"MySQL Error [{e.args[0]}]: {e.args[1]}")
        db.rollback()
        return False

def db_photo_delete(user_id, photo_path):
    """
    Deletes the photo record for the specified user ID and video path
    :param user_id: User ID (integer)
    :param photo_path: Video file path (string, must match stored path in database)
    :return: Boolean indicating success status of deletion
    """
    try:
        sql = "DELETE FROM tbl_video WHERE user_id = %s AND video_address = %s"
        cursor.execute(sql, (user_id, photo_path))
        db.commit()
        if cursor.rowcount > 0:
            print(f"Successfully deleted photo record: user_id={user_id}, path={photo_path}")
            return True
        else:
            print(f"No matching video photo found: user_id={user_id}, path={photo_path}")
            return False
    except MySQLdb.Error as e:
        print(f"MySQL Error [{e.args[0]}]: {e.args[1]}")
        db.rollback()
        return False