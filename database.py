""" This module contains table definitions for the png database, and a wrapper class
 for inserting and accessing data from the png database."""

import sqlite3
import typing
from os import path

TABLE = {}

# idat data + absolute file path and datetime added
TABLE["png_info"] = ("""CREATE TABLE IF NOT EXISTS png_info(
                     png_id INTEGER PRIMARY KEY AUTOINCREMENT,
                     file_path TEXT UNIQUE NOT NULL,
                     datetime_added_utc TEXT NOT NULL,
                     width INTEGER NOT NULL,
                     height INTEGER NOT NULL,
                     bit_depth INTEGER NOT NULL,
                     color_type INTEGER NOT NULL,
                     compression_method INTEGER NOT NULL,
                     filter_method INTEGER NOT NULL,
                     interlace_method INTEGER NOT NULL)""")

# everything returned by png_parser.read_chunk minus chunk data
TABLE["chunk_info"] = ("""CREATE TABLE IF NOT EXISTS chunk_info(
                       chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       png_id INTEGER NOT NULL,
                       chunk_length INTEGER NOT NULL,
                       chunk_type TEXT NOT NULL,
                       is_ancillary INTEGER NOT NULL,
                       is_private INTEGER NOT NULL,
                       is_reserved INTEGER NOT NULL,
                       is_safe_to_copy INTEGER NOT NULL,
                       chunk_crc INTEGER NOT NULL,
                       FOREIGN KEY (png_id)
                       REFERENCES png_info(png_id))""")

# idat chunk data takes up the most space so it gets its own table
TABLE["idat_chunk_data"] = ("""CREATE TABLE IF NOT EXISTS idat_chunk_data(
                            chunk_id INTEGER PRIMARY KEY,
                            png_id INTEGER NOT NULL,
                            chunk_data BLOB NOT NULL,
                            FOREIGN KEY (chunk_id)
                            REFERENCES chunk_info (chunk_id),
                            FOREIGN KEY (png_id)
                            REFERENCES png_info (png_id))""")

# other chunk data is still too large to go in chunk_info table so gets own table
TABLE["other_chunk_data"] = ("""CREATE TABLE IF NOT EXISTS other_chunk_data(
                             chunk_id INTEGER PRIMARY KEY,
                             png_id INTEGER NOT NULL,
                             chunk_data BLOB NOT NULL,
                             FOREIGN KEY (chunk_id)
                             REFERENCES chunk_info (chunk_id),
                             FOREIGN KEY (png_id)
                             REFERENCES png_info (png_id))""")

class Database:
    def __init__(self):
        self.con = None
        self.cur = None
        # we keep track of these for populating tables where they are foreign keys
        self.curr_png_id = None
        self.curr_chunk_id = None
        
    def connect(self):
        try:
            self.con = sqlite3.connect("db.db")
            self.con.row_factory = sqlite3.Row
            self.cur = self.con.cursor()
            for table_def in TABLE.values():
                self.cur.execute(table_def)
            print("Connected to db.db successfully\n")
            return True
        except sqlite3.Error as e:
            print(f"Error connecting to db.db:\n{e}")
            return False

    def insert_png_info(self, file_path, IHDR_info):
        IHDR_info_keys = ["width",
                          "height",
                          "bit_depth",
                          "color_type",
                          "compression_method",
                          "filter_method",
                          "interlace_method"
                          ]
        assert all(key in IHDR_info.keys() for key in IHDR_info_keys)
        IHDR_info["file_path"] = path.abspath(file_path)
        try:
            self.cur.execute("""INSERT INTO png_info (file_path,datetime_added_utc,width,height,bit_depth,color_type,compression_method,filter_method,interlace_method)
                                VALUES (:file_path, datetime('now'), :width, :height, :bit_depth, :color_type, :compression_method, :filter_method, :interlace_method)
                                RETURNING png_id""",
                             IHDR_info
                             )
            self.curr_png_id = self.cur.fetchone()[0]
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data into table png_info:\n{e}")
            return False

    def insert_chunk(self, chunk):
        chunk_data = chunk["chunk_data"]
        chunk_info = chunk
        assert self.curr_png_id is not None, "png_info must be populated before chunk tables"
        # bit janky
        if not self._insert_chunk_info(chunk_info): return False
        if chunk_info["chunk_type"] == "IDAT":
            if not self._insert_idat_chunk_data(chunk_data): return False
        else:
            if not self._insert_other_chunk_data(chunk_data): return False
        return True
    
    def _insert_chunk_info(self, chunk_info):
        chunk_info["png_id"] = self.curr_png_id
        try:
            self.cur.execute("""INSERT INTO chunk_info(png_id, chunk_length, chunk_type, is_ancillary, is_private, is_reserved, is_safe_to_copy, chunk_crc)
                                VALUES(:png_id, :chunk_length, :chunk_type, :is_ancillary, :is_private, :is_reserved, :is_safe_to_copy, :chunk_crc)
                                RETURNING chunk_id""",
                             chunk_info
                             )
            self.curr_chunk_id = self.cur.fetchone()[0]
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data into table chunk_info:\n{e}")
            return False

    def _insert_idat_chunk_data(self, chunk_data):
        try:
            self.cur.execute("""INSERT INTO idat_chunk_data(chunk_id, png_id, chunk_data)
                                VALUES(?, ?, ?)""",
                             (self.curr_chunk_id, self.curr_png_id, chunk_data)
                             )
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data into table other_chunk_data:\n{e}")
            return False
        
    def _insert_other_chunk_data(self, chunk_data):
        try:
            self.cur.execute("""INSERT INTO other_chunk_data(chunk_id, png_id, chunk_data)
                                VALUES(?, ?, ?)""",
                             (self.curr_chunk_id, self.curr_png_id, chunk_data)
                             )
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data into table other_chunk_data:\n{e}")
            return False

    def get_random_png_file(self):
        """ Chooses a random png file from png_info, and returns the chunks
        and information needed to decode and plot the image. """
        try:
            self.cur.execute("SELECT png_id FROM png_info ORDER BY RANDOM() LIMIT 1")
            random_id = self.cur.fetchone()[0]
            self.cur.execute("""SELECT
                                file_path,
                                width,
                                height,
                                bit_depth,
                                color_type
                                FROM png_info
                                WHERE png_id = ?""",
                             [random_id]
                             )
            data = self.cur.fetchone()
            # can make this nicer by making row factory give a dict
            file_path = data[0]
            IHDR_info = {}
            IHDR_info["width"], IHDR_info["height"], IHDR_info["bit_depth"], IHDR_info["color_type"] = data["width"], data["height"], data["bit_depth"], data["color_type"]
            
            self.cur.execute("""SELECT
                                chunk_type,
                                chunk_length,
                                other_chunk_data.chunk_data
                                FROM chunk_info
                                JOIN other_chunk_data ON chunk_info.chunk_id = other_chunk_data.chunk_id
                                WHERE chunk_info.png_id = ?""", [random_id])
            other_chunks = self.cur.fetchall()
            PLTE_chunk = None
            for chunk in other_chunks:
                if chunk["chunk_type"] == "PLTE":
                    PLTE_chunk = {}
                    PLTE_chunk["chunk_type"] = chunk["chunk_type"]
                    PLTE_chunk["chunk_data"] = chunk["chunk_data"]
                    PLTE_chunk["chunk_length"] = chunk["chunk_length"]
                    break
            self.cur.execute("""SELECT
                                chunk_type,
                                idat_chunk_data.chunk_data
                                FROM chunk_info
                                JOIN idat_chunk_data ON chunk_info.chunk_id = idat_chunk_data.chunk_id
                                WHERE chunk_info.png_id = ?""", [random_id])
            IDAT_chunks = self.cur.fetchall()
            IDAT_data = b''.join([data["chunk_data"] for data in IDAT_chunks])
            return IHDR_info, PLTE_chunk, IDAT_data
        
        except sqlite3.Error as e:
            print(f"Error getting random png file:\n{e}")
            return None, None, None

    def save_changes(self):
        self.con.commit()
        
    def close(self):
        self.cur.close()
        self.con.close()
