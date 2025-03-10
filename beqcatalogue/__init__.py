import csv
import os
import re
from operator import itemgetter
from typing import Tuple
from urllib import parse

import json

from itertools import groupby
from markdown.extensions.toc import slugify

from iir import xml_to_filt


def extract_from_repo(path1: str, path2: str, content_type: str):
    '''
    extracts beq_metadata of following format
           <beq_metadata>
                <beq_title>9</beq_title>
                <beq_alt_title />
                <beq_sortTitle>9</beq_sortTitle>
                <beq_year>2009</beq_year>
                <beq_spectrumURL>https://i.imgur.com/aRic6II.jpg</beq_spectrumURL>
                <beq_pvaURL>https://i.imgur.com/4DReGr5.jpg</beq_pvaURL>
                <beq_edition />
                <beq_season />
                <beq_note />
                <beq_warning />
                <beq_gain>-1 gain</beq_gain>
                <beq_language>English</beq_language>
                <beq_source>Disc</beq_source>
                <beq_author>aron7awol</beq_author>
                <beq_avs>https://www.avsforum.com/threads/bass-eq-for-filtered-movies.2995212/post-57282106</beq_avs>
                <beq_theMovieDB>12244</beq_theMovieDB>
                <beq_poster>/usfcQZRqdXTSSQ55esiPHJZKkIU.jpg</beq_poster>
                <beq_runtime>79</beq_runtime>
                <beq_audioTypes>
                        <audioType>DTS-HD MA 5.1</audioType>
                </beq_audioTypes>
                <beq_genres>
                        <genre id="878">Science Fiction</genre>
                        <genre id="16">Animation</genre>
                        <genre id="12">Adventure</genre>
                        <genre id="28">Action</genre>
                        <genre id="53">Thriller</genre>
                </beq_genres>
            </beq_metadata>

        new season format replaces beq_season with

               <beq_season id="92137">
                   <number>1</number>
                   <poster>/q1X7Ev3Hcr0Q7aUiWgw1ZUZf1QZ.jpg</poster>
                   <episodes count="8">1,2,3,4,5,6,7,8</episodes>
               </beq_season>

    :return:
    '''
    import xml.etree.ElementTree as ET
    import glob
    elements = []
    for xml in glob.glob(f"{path1}{path2}/**/*.xml", recursive=True):
        et_tree = ET.parse(str(xml))
        root = et_tree.getroot()
        file_name = xml[:-4]
        meta = {
            'repo_file': str(xml),
            'file_name': file_name.split('/')[-1],
            'file_path': '/'.join(file_name[len(path1):].split('/')[:-1]),
            'content_type': content_type
        }
        for child in root:
            if child.tag == 'beq_metadata':
                for m in child:
                    if len(m) == 0:
                        txt = m.text
                        if txt:
                            meta[m.tag[4:]] = m.text
                    elif m.tag == 'beq_audioTypes':
                        audio_types = [c.text.strip() for c in m]
                        meta['audioType'] = [at for at in audio_types if at]
                    elif m.tag == 'beq_season':
                        parse_season(m, meta, xml)
                    elif m.tag == 'beq_genres':
                        genres = [c.text.strip() for c in m]
                        meta['genres'] = [at for at in genres if at]
        filts = [f for f in xml_to_filt(xml, unroll=True)]
        meta['jsonfilters'] = [f.to_map() for f in filts]
        meta['filters'] = '^'.join([str(f) for f in filts])
        elements.append(meta)
    return elements


def parse_season(m, meta, xml):
    try:
        meta['season'] = {'id': m.attrib['id']}
        for c in m:
            if c.tag == 'episodes':
                meta['season']['episode_count'] = c.attrib['count']
            meta['season'][c.tag] = c.text
        complete = True
        if 'episode_count' in meta['season'] and 'episodes' in meta['season']:
            count = int(meta['season']['episode_count'])
            epi_txt = meta['season']['episodes']
            if epi_txt:
                episodes = [int(e) for e in meta['season']['episodes'].split(',')]
                for c in range(count):
                    if c + 1 not in episodes:
                        complete = False
        meta['season']['complete'] = complete
    except:
        print(f"Unable to parse season info from {xml}")


def group_mobe1969_film_content(content_meta):
    by_title = {}
    fallback_pattern = re.compile(r'(.*) \((\d{4})\)(?: *\(.*\))? (.*)')
    for meta in content_meta:
        if 'title' in meta:
            title = meta['title']
            if title in by_title:
                by_title[title].append(meta)
            else:
                by_title[title] = [meta]
        else:
            json = {
                'title': meta['file_name'],
                'author': 'mobe1969',
                'content_type': meta['content_type']
            }
            match = fallback_pattern.match(meta['file_name'])
            if match:
                json['title'] = match.group(1)
                json['year'] = match.group(2)
                json['audioTypes'] = match.group(3).split('+')
            print(f"Missing title entry, extracted {json}")
            json['filters'] = meta['jsonfilters']
            json_catalogue.append(json)
    return by_title


def group_mobe1969_tv_content(content_meta):
    by_title = {}
    fallback_pattern = re.compile(r'(.*) \((\d{4})\)(?: *\(.*\))? (.*)')
    for meta in content_meta:
        if 'title' in meta:
            title = meta['title']
            if title[-4:-2] == ' E' and title[-2:].isdigit():
                meta['episode'] = title[-2:]
                title = title[:-4]
                meta['title'] = title
            elif 'note' in meta:
                note = meta['note']
                if note[0] == 'E':
                    if note[1:].isdigit():
                        meta['episode'] = note[1:]
                    elif '-' in note[1:]:
                        vals = [int(i) for i in note[1:].split('-')]
                        if len(vals) == 2:
                            meta['episode'] = ','.join([str(e) for e in range(vals[0], vals[1] + 1)])
                elif note[0] == 'S':
                    frags = note.split('-')
                    if len(frags) == 2:
                        if frags[1][0] == 'E':
                            if frags[1][1:].isdigit():
                                meta['episode'] = frags[1][1:]
                if 'episode' not in meta:
                    print(f"Unknown note format in {meta}")
            if title in by_title:
                by_title[title].append(meta)
            else:
                by_title[title] = [meta]
        else:
            json = {
                'title': meta['file_name'],
                'author': 'mobe1969',
                'content_type': meta['content_type']
            }
            match = fallback_pattern.match(meta['file_name'])
            if match:
                json['title'] = match.group(1)
                json['year'] = match.group(2)
                json['audioTypes'] = match.group(3).split('+')
            print(f"Missing title entry, extracted {json}")
            json['filters'] = meta['jsonfilters']
            json_catalogue.append(json)
    return by_title


def process_mobe1969_content_from_repo(content_meta, index_entries, content_type):
    ''' converts beq_metadata into md '''
    if content_type == 'film':
        by_title = group_mobe1969_film_content(content_meta)
    else:
        by_title = group_mobe1969_tv_content(content_meta)
    for title, metas in by_title.items():
        title_md = slugify(title, '-')
        with open(f"docs/mobe1969/{title_md}.md", mode='w+') as content_md:
            generate_content_page(title_md, metas, content_md, index_entries, 'mobe1969', content_type)


def process_aron7awol_content_from_repo(content_meta, index_entries, content_type):
    ''' converts beq_metadata into md '''
    for post_id, metas in group_aron7awol_content(content_meta, content_type).items():
        with open(f"docs/aron7awol/{post_id}.md", mode='w+') as content_md:
            generate_content_page(post_id, metas, content_md, index_entries, 'aron7awol', content_type)


def group_aron7awol_content(content_meta, content_type) -> dict:
    grouped_meta = {}
    if content_type == 'film':
        for meta in content_meta:
            if 'avs' in meta:
                avs = meta['avs']
                idx = avs.find('post?id=')
                avs_post_id = None
                if idx == -1:
                    idx = avs.find('post-')
                    if idx == -1:
                        print(f"Unparsable post id {meta['repo_file']} - {avs}")
                    else:
                        avs_post_id = avs[idx + 5:]
                else:
                    avs_post_id = avs[idx + 8:]
                if avs_post_id:
                    if avs_post_id in grouped_meta:
                        grouped_meta[avs_post_id].append(meta)
                    else:
                        grouped_meta[avs_post_id] = [meta]
            else:
                print(f"Missing beq_avs entry for {meta['repo_file']}")
    else:
        for meta in content_meta:
            if 'title' in meta:
                title = slugify(meta['title'], '-')
                if title in grouped_meta:
                    grouped_meta[title].append(meta)
                else:
                    grouped_meta[title] = [meta]
    return grouped_meta


def generate_content_page(page_name, metas, content_md, index_entries, author, content_type):
    if content_type == 'film':
        generate_film_content_page(page_name, metas, content_md, index_entries, author)
    else:
        generate_tv_content_page(page_name, metas, content_md, index_entries, author)


def generate_film_content_page(page_name, metas, content_md, index_entries, author):
    ''' prints the md content page '''
    print(f"# {metas[0]['title']}", file=content_md)
    print("", file=content_md)
    print(f"* Author: {author}", file=content_md)
    if 'avs' in metas[0]:
        print(f"* [Forum Post]({metas[0]['avs']})", file=content_md)
    production_years = {m['year'] for m in metas}
    img_idx = 0
    if len(production_years) == 1:
        print(f"* Production Year: {production_years.pop()}", file=content_md)
    print("", file=content_md)
    for meta in sorted(metas, key=lambda m: ', '.join(m.get('audioType', ''))):
        if 'pvaURL' not in meta and 'spectrumURL' not in meta:
            print(f"No charts found in {meta}")
        else:
            audio_type = meta.get('audioType', '')
            beq_catalogue_url = ''
            actual_img_links = []
            if 'pvaURL' in meta:
                actual_img_links.append(meta['pvaURL'])
            if 'spectrumURL' in meta:
                actual_img_links.append(meta['spectrumURL'])
            if audio_type:
                linked_content_format = ', '.join(audio_type)
                print(f"## {linked_content_format}", file=content_md)
                print("", file=content_md)
                if production_years:
                    print(f"* Production Year: {meta['year']}", file=content_md)
                    print("", file=content_md)
                for img in actual_img_links:
                    print(f"![img {img_idx}]({img})", file=content_md)
                    print('', file=content_md)

                bd_url = generate_index_entry(author, page_name, linked_content_format, meta['title'], meta['year'],
                                              meta.get('avs', None), len(metas) > 1, index_entries)
                prefix = 'https://beqcatalogue.readthedocs.io/en/latest'
                beq_catalogue_url = f"{prefix}/{author}/{page_name}/#{slugify(linked_content_format, '-')}"
                cols = [
                    meta['title'],
                    meta['year'],
                    linked_content_format,
                    author,
                    meta.get('avs', ''),
                    beq_catalogue_url,
                    bd_url,
                    meta['filters']
                ]
                db_writer.writerow(cols + actual_img_links)
            else:
                print(f"No audioTypes in {metas[0]['title']}")
            json_catalogue.append({
                'title': meta['title'],
                'year': meta['year'],
                'audioTypes': meta.get('audioType', []),
                'content_type': 'film',
                'author': author,
                'catalogue_url': beq_catalogue_url,
                'filters': meta['jsonfilters'],
                'images': actual_img_links,
                'warning': meta.get('warning', ''),
                'mv': meta.get('gain', '0'),
                'avs': meta.get('avs', ''),
                'sortTitle': meta.get('sortTitle', ''),
                'edition': meta.get('edition', ''),
                'note': meta.get('note', ''),
                'language': meta.get('language', ''),
                'source': meta.get('source', ''),
                'overview': meta.get('overview', ''),
                'theMovieDB': meta.get('theMovieDB', ''),
                'rating': meta.get('rating', ''),
                'runtime': meta.get('runtime', '0'),
                'genres': meta.get('genres', [])
            })


def format_season_episode(m) -> Tuple[str, str, str, str]:
    long_season_episode = ''
    short_season_episode = ''
    season = ''
    episodes = ''
    if 'season' in m:
        season_meta = m['season']
        if isinstance(season_meta, str):
            season = season_meta
            long_season_episode = f"Season {season}"
            short_season_episode = f"S{season}"
            if 'episode' in m:
                episodes = m['episode']
                long_season_episode += f" Episode {episodes}"
                short_season_episode += f"E{episodes}"
        else:
            season = season_meta['number']
            long_season_episode = f"Season {season}"
            short_season_episode = f"S{season}"
            if not season_meta['complete']:
                episodes = season_meta['episodes']
                to_print = episodes
                s = ''
                if ',' in episodes:
                    epi_nums = [int(e) for e in episodes.split(',')]
                    if len(epi_nums) > 1:
                        ranges = []
                        for k, g in groupby(enumerate(epi_nums), lambda t: t[0] - t[1]):
                            group = list(map(itemgetter(1), g))
                            if group[0] == group[-1]:
                                ranges.append(f"{group[0]}")
                            else:
                                ranges.append(f"{group[0]}-{group[-1]}")
                        to_print = ', '.join(ranges)
                        s = 's'
                long_season_episode += f" Episode{s} {to_print}"
                short_season_episode += f"E{to_print}"
    return long_season_episode, short_season_episode, season, episodes


def generate_tv_content_page(page_name, metas, content_md, index_entries, author):
    ''' prints the md content page '''
    print(f"# {metas[0]['title']}", file=content_md)
    print("", file=content_md)
    print(f"* Author: {author}", file=content_md)
    img_idx = 0
    print("", file=content_md)

    def sort_meta(m):
        sort_key = ''
        if 'season' in m:
            season_meta = m['season']
            if isinstance(season_meta, str):
                sort_key = season_meta
                if 'episode' in m:
                    sort_key += m['episode']
            else:
                sort_key = season_meta['number']
                if not season_meta['complete']:
                    sort_key += season_meta['episodes']
        return sort_key

    for meta in sorted(metas, key=sort_meta):
        audio_type = meta.get('audioType', '')
        linked_content_format = ''
        actual_img_links = []
        long_season, short_season, season, episodes = format_season_episode(meta)
        if 'pvaURL' in meta:
            actual_img_links.append(meta['pvaURL'])
        if 'spectrumURL' in meta:
            actual_img_links.append(meta['spectrumURL'])
        if long_season:
            print(f"## {long_season}", file=content_md)
            print("", file=content_md)
        if audio_type:
            linked_content_format = ', '.join(audio_type)
            print(f"* {linked_content_format}", file=content_md)
            print("", file=content_md)
        if 'avs' in meta:
            print(f"* [Forum Post]({meta['avs']})", file=content_md)
        if 'year' in meta:
            print(f"* Production Year: {meta['year']}", file=content_md)
            print("", file=content_md)
        for img in actual_img_links:
            print(f"![img {img_idx}]({img})", file=content_md)
            print('', file=content_md)

        extra_slug = f"#{slugify(long_season, '-')}" if long_season else ''
        bd_url = generate_index_entry(author, page_name, linked_content_format, f"{meta['title']} {short_season}",
                                      meta['year'], meta.get('avs', None), len(metas) > 1, index_entries,
                                      content_type='TV', extra_slug=extra_slug)
        prefix = 'https://beqcatalogue.readthedocs.io/en/latest'
        slugified_link = f"/{extra_slug}" if extra_slug else ''
        beq_catalogue_url = f"{prefix}/{author}/{page_name}{slugified_link}"
        cols = [
            meta['title'],
            meta['year'],
            linked_content_format,
            author,
            meta.get('avs', ''),
            beq_catalogue_url,
            bd_url,
            meta['filters']
        ]
        db_writer.writerow(cols + actual_img_links)

        # TODO remove once metadata is added
        if author == 'mobe1969' and len(actual_img_links) == 0:
            from urllib.parse import quote
            print(f"Generating img link for missing meta in {meta}")
            fp = meta['file_path'].replace('TV BEQs', 'TV Series')
            img = f"https://gitlab.com/Mobe1969/beq-reports/-/raw/master/{quote(fp)}/{quote(meta['file_name'])}.jpg"
            actual_img_links = [img]
            print(f"![img {img_idx}]({img})", file=content_md)
            print('', file=content_md)

        json_catalogue.append({
            'title': meta['title'],
            'year': meta['year'],
            'audioTypes': meta.get('audioType', []),
            'content_type': 'TV',
            'author': author,
            'catalogue_url': beq_catalogue_url,
            'filters': meta['jsonfilters'],
            'images': actual_img_links,
            'warning': meta.get('warning', ''),
            'season': season,
            'episode': episodes,
            'mv': meta.get('gain', '0'),
            'avs': meta.get('avs', ''),
            'sortTitle': meta.get('sortTitle', ''),
            'edition': meta.get('edition', ''),
            'note': meta.get('note', ''),
            'language': meta.get('language', ''),
            'source': meta.get('source', ''),
            'overview': meta.get('overview', ''),
            'theMovieDB': meta.get('theMovieDB', ''),
            'rating': meta.get('rating', ''),
            'genres': meta.get('genres', [])
        })


def generate_index_entry(author, page_name, content_format, content_name, year, avs_url, multiformat, index_entries,
                         content_type='film', extra_slug=None):
    ''' dumps the summary info to the index page '''
    escaped = parse.quote(content_name)
    mdb_url = f"https://www.themoviedb.org/search?query={escaped}"
    rt_url = f"https://www.rottentomatoes.com/search?search={escaped}"
    bd_url = f"https://www.blu-ray.com/movies/search.php?keyword={escaped}&submit=Search&action=search&"
    if content_type == 'film':
        extra_slug = f"#{slugify(content_format, '-')}" if multiformat is True else ''
    avs_link = f"[avsforum]({avs_url})" if avs_url else ''
    index_entries.append(
        f"| [{content_name}](./{author}/{page_name}.md{extra_slug}) | {content_type} | {year} | {content_format} | {'Yes' if multiformat else 'No'} | {avs_link} [blu-ray]({bd_url}) [themoviedb]({mdb_url}) [rottentoms]({rt_url}) |")
    return bd_url


if os.getcwd() == os.path.dirname(os.path.abspath(__file__)):
    print(f"Switching CWD from {os.getcwd()}")
    os.chdir('..')
else:
    print(f"CWD: {os.getcwd()}")

if __name__ == '__main__':
    aron7awol_films = extract_from_repo('.input/bmiller/miniDSPBEQ/', 'Movie BEQs', 'film')
    print(f"Extracted {len(aron7awol_films)} aron7awol film catalogue entries")
    aron7awol_tv = extract_from_repo('.input/bmiller/miniDSPBEQ/', 'TV Shows BEQ', 'TV')
    print(f"Extracted {len(aron7awol_tv)} aron7awol TV catalogue entries")

    mobe1969_films = extract_from_repo('.input/Mobe1969/miniDSPBEQ/', 'Movie BEQs', 'film')
    print(f"Extracted {len(mobe1969_films)} mobe1969 film catalogue entries")
    mobe1969_tv = extract_from_repo('.input/Mobe1969/miniDSPBEQ/', 'TV BEQs', 'TV')
    print(f"Extracted {len(mobe1969_tv)} mobe1969 TV catalogue entries")

    json_catalogue = []

    with open('docs/database.csv', 'w+', newline='') as db_csv:
        db_writer = csv.writer(db_csv)
        db_writer.writerow(['Title', 'Year', 'Format', 'Author', 'AVS', 'Catalogue', 'blu-ray.com', 'filters'])
        index_entries = []
        process_aron7awol_content_from_repo(aron7awol_films, index_entries, 'film')
        process_aron7awol_content_from_repo(aron7awol_tv, index_entries, 'TV')
        with open('docs/aron7awol.md', mode='w+') as index_md:
            print(f"# aron7awol", file=index_md)
            print('', file=index_md)
            print(f"| Title | Type | Year | Format | Multiformat? | Links |", file=index_md)
            print(f"|-|-|-|-|-|-|", file=index_md)
            for i in sorted(index_entries, key=str.casefold):
                print(i, file=index_md)

        index_entries = []
        process_mobe1969_content_from_repo(mobe1969_films, index_entries, 'film')
        process_mobe1969_content_from_repo(mobe1969_tv, index_entries, 'TV')
        with open('docs/mobe1969.md', mode='w+') as index_md:
            print(f"# Mobe1969", file=index_md)
            print('', file=index_md)
            print(f"| Title | Type | Year | Format | Multiformat? | Links |", file=index_md)
            print(f"|-|-|-|-|-|-|", file=index_md)
            for i in sorted(index_entries, key=str.casefold):
                print(i, file=index_md)
            print('', file=index_md)

    with open('docs/database.json', 'w+') as db_json:
        json.dump(json_catalogue, db_json, indent=0)
