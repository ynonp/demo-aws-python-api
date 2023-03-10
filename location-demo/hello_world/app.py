from flask import jsonify, request
from flask_lambda import FlaskLambda
import boto3

app = FlaskLambda(__name__)
client = boto3.client('location')

@app.route('/place')
def place():
    place_id = request.args.get('id')
    res = client.get_place(PlaceId=place_id, IndexName='my-place-index')
    return jsonify(res["Place"])

@app.route('/suggestions')
def suggestions():
    q = request.args.get('q')
    res = client.search_place_index_for_suggestions(Text=q, IndexName='my-place-index', FilterCountries=['ISR'])
    return jsonify(res["Results"])

@app.route('/hello')
def hello():
    return jsonify("Hello world")