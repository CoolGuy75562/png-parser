""" This module contains table definitions for the png database,
and a wrapper class for inserting and accessing data from the png database."""
# Copyright (C) 2024  CoolGuy75562
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

import sqlite3
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

# other chunk data is too large to go in chunk_info table so gets own table
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
        # we keep track of these for populating tables
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
            self.cur.execute("""INSERT INTO png_info(
                                    file_path,
                                    datetime_added_utc,
                                    width,
                                    height,
                                    bit_depth,
                                    color_type,
                                    compression_method,
                                    filter_method,
                                    interlace_method)
                                VALUES (
                                    :file_path,
                                    datetime('now'),
                                    :width,
                                    :height,
                                    :bit_depth,
                                    :color_type,
                                    :compression_method,
                                    :filter_method,
                                    :interlace_method)
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
        assert self.curr_png_id is not None, \
            "png_info must be populated before chunk tables"
        # bit janky
        if not self._insert_chunk_info(chunk_info):
            return False
        if chunk_info["chunk_type"] == "IDAT":
            if not self._insert_idat_chunk_data(chunk_data):
                return False
        else:
            if not self._insert_other_chunk_data(chunk_data):
                return False
        return True

    def _insert_chunk_info(self, chunk_info):
        chunk_info["png_id"] = self.curr_png_id
        try:
            self.cur.execute("""INSERT INTO chunk_info(
                                    png_id,
                                    chunk_length,
                                    chunk_type,
                                    is_ancillary,
                                    is_private,
                                    is_reserved,
                                    is_safe_to_copy,
                                    chunk_crc)
                                VALUES(
                                    :png_id,
                                    :chunk_length,
                                    :chunk_type,
                                    :is_ancillary,
                                    :is_private,
                                    :is_reserved,
                                    :is_safe_to_copy,
                                    :chunk_crc)
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
            self.cur.execute("""INSERT INTO idat_chunk_data(
                                    chunk_id,
                                    png_id,
                                    chunk_data)
                                VALUES(?, ?, ?)""",
                             (self.curr_chunk_id, self.curr_png_id, chunk_data)
                             )
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data into table other_chunk_data:\n{e}")
            return False

    def _insert_other_chunk_data(self, chunk_data):
        try:
            self.cur.execute("""INSERT INTO other_chunk_data(
                                    chunk_id,
                                    png_id,
                                    chunk_data)
                                VALUES(?, ?, ?)""",
                             (self.curr_chunk_id, self.curr_png_id, chunk_data)
                             )
            return True
        except sqlite3.Error as e:
            print(f"Error inserting data into table other_chunk_data:\n{e}")
            return False

    def get_random_png_file(self, width_lim=None):
        """ Chooses a random png file from png_info, and returns the chunks
        and information needed to decode and plot the image. """
        try:
            if width_lim:
                self.cur.execute("""SELECT png_id
                                    FROM png_info
                                    WHERE NOT interlace_method = 1
                                        AND width < ?
                                        AND NOT bit_depth = 16
                                    ORDER BY RANDOM() LIMIT 1""",
                                 [width_lim]
                                 )
            else:
                self.cur.execute("""SELECT png_id
                                    FROM png_info
                                    WHERE NOT interlace_method = 1
                                    ORDER BY RANDOM() LIMIT 1""")
            random_id = self.cur.fetchone()
            if random_id is None:
                return None, None, None
            else:
                random_id = random_id[0]
            self.cur.execute("""SELECT
                                    file_path,
                                    width,
                                    height,
                                    bit_depth,
                                    color_type,
                                    interlace_method
                                FROM png_info
                                WHERE png_id = ?""",
                             [random_id]
                             )
            data = self.cur.fetchone()
            # can make this nicer by making row factory give a dict
            IHDR_info = {}
            IHDR_info["width"] = data["width"]
            IHDR_info["height"] = data["height"]
            IHDR_info["bit_depth"] = data["bit_depth"]
            IHDR_info["color_type"] = data["color_type"]
            IHDR_info["interlace_method"] = data["interlace_method"]
            self.cur.execute("""SELECT
                                    chunk_type,
                                    chunk_length,
                                    other_chunk_data.chunk_data
                                FROM chunk_info
                                JOIN other_chunk_data
                                    ON chunk_info.chunk_id =
                                       other_chunk_data.chunk_id
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
                                JOIN idat_chunk_data
                                    ON chunk_info.chunk_id =
                                       idat_chunk_data.chunk_id
                                WHERE chunk_info.png_id = ?""", [random_id])
            IDAT_chunks = self.cur.fetchall()
            IDAT_data = b''.join([data["chunk_data"] for data in IDAT_chunks])
            return IHDR_info, PLTE_chunk, IDAT_data

        except sqlite3.Error as e:
            print(f"Error getting random png file:\n{e}")
            return None, None, None

    def get_first_n_infos(self, n: int, **kwargs
                          ) -> tuple[list[str], list[dict], list[dict]]:
        if kwargs:
            # chunk name part temporary. silly to concat first
            kw_conds = {'color_type': ' = :',
                        'bit_depth': ' = :',
                        'interlace_method': ' = :',
                        'width': ' < :',
                        'height': ' < :',
                        'chunk_name': " chunk_types LIKE '%' || :chunk_name || '%' "
                        }
            query = (("SELECT file_path, width, height, bit_depth, "
                      "color_type, compression_method, filter_method, "
                      "interlace_method, "
                      "(SELECT GROUP_CONCAT(chunk_type) FROM chunk_info "
                      "WHERE png_info.png_id = chunk_info.png_id) "
                      "AS chunk_types "
                      "FROM png_info "
                      "WHERE ")
                     + ' AND '.join(kw + kw_conds[kw] + kw if kw != 'chunk_name'
                                    else kw_conds[kw]
                                    for kw in kwargs.keys()
                                    )
                     + " LIMIT :n")
        else:
            query = """SELECT
                           file_path,
                           width,
                           height,
                           bit_depth,
                           color_type,
                           compression_method,
                           filter_method,
                           interlace_method,
                           (SELECT GROUP_CONCAT(chunk_type)
                            FROM chunk_info
                            WHERE png_info.png_id = chunk_info.png_id
                           ) AS chunk_types
                           FROM png_info
                           LIMIT :n"""
        kwargs['n'] = n;

        try:
            self.cur.execute(query, kwargs)
            data = self.cur.fetchall()
            file_paths = [row["file_path"] for row in data]
            # absolutely disgusting
            # TODO: row factory
            png_infos = [{"width": row["width"],
                          "height": row["height"],
                          "bit_depth": row["bit_depth"],
                          "color_type": row["color_type"],
                          "compression_method": row["compression_method"],
                          "filter_method": row["filter_method"],
                          "interlace_method": row["interlace_method"]
                          }
                         for row in data
                         ]
            png_chunkss = [row["chunk_types"].split(',') for row in data]

            return file_paths, png_infos, png_chunkss

        except sqlite3.Error as e:
            print(e)
            return None, None, None

    def save_changes(self):
        self.con.commit()

    def close(self):
        self.cur.close()
        self.con.close()
