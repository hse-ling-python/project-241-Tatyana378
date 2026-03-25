import os
import re
from flask import Flask
from flask import render_template, request, redirect, url_for, flash
from functools import lru_cache
from slugify import slugify

import stanza
from latino import Translator

stanza.download('la')
nlp = stanza.Pipeline('la', processors='tokenize,pos,lemma,depparse')
translator = Translator("en")

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXTS_DIR = os.path.join(BASE_DIR, 'texts')

#---------------------------------------------------------------------------
def sent_info(word):
    # словарь по предложению
    dict_sent = {}
    doc = nlp(word)
    sent = doc.sentences[0]
    for w in sent.words:
        lemma, pos, feats = w.lemma, w.upos, w.feats
        translations = []
        try:
            w_tr = translator.translate(lemma)
            for translated in w_tr:
                translations.append(translated.traduzione[0])
        except:
            translations.append('-')

        feats_dict = {}
        if feats:
            for f in feats.split('|'):
                name, value = f.split('=')
                feats_dict[name] = value
        else:
            feats_dict = '-'
        

        dict_sent[w.text] = {
            'lemma': lemma,
            'pos': pos,
            'features': feats_dict,
            'translations': translations
        }

    return dict_sent

def text_info(word):
    # словарь по тексту
    dict_sents = {}
    doc = nlp(word)

    i = 0
    for sentence in doc.sentences:
        sent_dict = sent_info(sentence)
        dict_sents[i] = sent_dict

        i += 1

    return dict_sents

def parse_text_file(filepath):
    # создание библиотеки
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parts = content.split('\n\n', 1)
    header = parts[0]
    body = parts[1] if len(parts) > 1 else ''
    
    data = {}
    for line in header.split('\n'):
        if line.startswith('#'):
            match = re.match(r'#\s*([\w]+):\s*(.*)', line)
            key, value = match.groups()
            data[key.strip()] = value.strip()
    
    body = parts[1] if len(parts) > 1 else ''
    body = re.sub(r'<[^>]+>', '', body)
    
    return {
        'id': data.get('ID', ''),
        'author': data.get('author', 'Unknown'),
        'title': data.get('title', 'Untitled'),
        'lang': data.get('language', 'la'),
        'content': body.strip(),
        'availability': data.get('availability', '')
    }
#---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('main.html')

# СЛОВАРИК --------------------------------
@app.route('/done_dict', methods=['POST'])
def done_dict():
    inp_text = request.form.get('text')
    ready_dict = sent_info(inp_text)
    out_text = ''
    for w, par in ready_dict.items():
        line = ''
        if w.isalpha():
            
            try:
                tense = par['features']['Tense']
            except:
                tense = ""
            try:
                pers = par['features']['Person']
            except:
                pers = "-"

            if par['translations']:
                if par['pos'] == 'VERB':
                    if tense:
                        line += f"{w} — {par['lemma']} ({par['pos']}), ФОРМА: {par['features']['Aspect']} (вид) {tense} (время) {par['features']['Voice']} (залог), Pers. {pers} {par['features']['Number']}. ПЕРЕВОД: {' '.join(par['translations'])}\n"
                    else:
                        line += f"{w} — {par['lemma']} ({par['pos']}), ФОРМА: {par['features']['Aspect']} (вид) {par['features']['VerbForm']} {par['features']['Voice']} (залог), Pers. {pers} {par['features']['Number']}. ПЕРЕВОД: {' '.join(par['translations'])}\n"
                elif par['pos'] == 'NOUN' or par['pos'] == 'ADJ':
                    line += f"{w} — {par['lemma']} ({par['pos']}), ФОРМА: {par['features']['Case']} (падеж) {par['features']['Number']} (число) {par['features']['Gender']} (род). ПЕРЕВОД: {' '.join(par['translations'])}\n"
                else:
                    line += f"{w} — {par['lemma']} ({par['pos']}), ПЕРЕВОД: {' '.join(par['translations'])}\n"
                out_text += line
                out_text += '<br>'
            else:
                if par['pos'] == 'VERB':
                    if tense:
                        line += f"{w} — {par['lemma']} ({par['pos']}), ФОРМА: {par['features']['Aspect']} (вид) {tense} (время) {par['features']['Voice']} (залог), Pers. {pers} {par['features']['Number']}.\n"
                    else:
                        line += f"{w} — {par['lemma']} ({par['pos']}), ФОРМА: {par['features']['Aspect']} (вид) {par['features']['VerbForm']} {par['features']['Voice']} (залог), Pers. {pers} {par['features']['Number']}.\n"
                elif par['pos'] == 'NOUN' or par['pos'] == 'ADJ':
                    line += f"{w} — {par['lemma']} ({par['pos']}), ФОРМА: {par['features']['Case']} (падеж) {par['features']['Number']} (число) {par['features']['Gender']} (род).\n"
                else:
                    line += f"{w} — {par['lemma'] ({par['pos']})}\n"
                out_text += line
                out_text += '<br>'

    return render_template('done_d.html', ready_dict=out_text)

# БИБЛИОТЕКА --------------------------------

@lru_cache(maxsize=1)
def load_all_texts():
    texts_by_author = {}
    
    for filename in os.listdir(TEXTS_DIR):
        if filename.endswith('.txt'):
            filepath = os.path.join(TEXTS_DIR, filename)
            text = parse_text_file(filepath)
            author = text['author']
            author_slug = slugify(author)
            
            if author_slug not in texts_by_author:
                texts_by_author[author_slug] = {
                    'name': author,
                    'texts': []
                }
            texts_by_author[author_slug]['texts'].append(text)
    
    for author_data in texts_by_author.values():
        author_data['texts'].sort(key=lambda x: x['title'])
    
    return texts_by_author

@app.route('/library')
def library_authors():
    # все авторы
    texts = load_all_texts()
    authors = sorted(
        [{'slug': slug, 'name': data['name'], 'count': len(data['texts'])} 
         for slug, data in texts.items()],
        key=lambda x: x['name']
    )

    return render_template('authors.html', authors=authors)

@app.route('/library/<author_slug>')
def author_texts(author_slug):
    # все тексты одного автора
    texts = load_all_texts()
    authr = texts[author_slug]['name']
    txts = texts[author_slug]['texts']
    author_slug = author_slug


    return render_template(
        'texts_by_author.html',
        author=authr,
        texts=txts,
        author_slug=author_slug
    )

@app.route('/library/<author_slug>/<text_id>')
def view_text(author_slug, text_id):
    # один текст
    texts = load_all_texts()
    
    text = next((t for t in texts[author_slug]['texts'] if t['id'] == text_id), None)
    
    return render_template(
        'text_view.html',
        text=text,
        author_name=texts[author_slug]['name'],
        author_slug=author_slug
    )


#--------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=False)