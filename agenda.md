# AWS + Python Serverless Demo

Sign up to AWS free tier:
[https://portal.aws.amazon.com/billing/signup#/account](https://portal.aws.amazon.com/billing/signup#/account)

Download / Install AWS CLI:
[https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

Get AWS Credentials (to use in `aws configure`):
[https://us-east-1.console.aws.amazon.com/iamv2/home#/security_credentials](https://us-east-1.console.aws.amazon.com/iamv2/home#/security_credentials)

Download / Install SAM CLI:
[https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)

## Part 1-

- What's a serverless API? (AWS / GCP / Oracle / Azure)
  * Lambda
  * Location
  * [AWS Python Location API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/location.html)

- Create a first serverless python API with sam
  - Free tier


- Modify the code to use AWS location service

- Create a "suggestions" API endpoint that takes a query string and returns list of possible places

- Deploy and fix bugs



## Part 2-

- Working with multiple endpoints

- Install flask-lambda module

- Convert the app to flask

- Add a second (and third) endpoint

- Deploy and fix bugs







# Commands used in part 1

Get current AWS account ID (to verify it's installed):

```
aws sts get-caller-identity --query "Account" --output text
```

Init a new sam project
```
sam init --runtime python3.9 --name location-demo
```

start a local server and check if everything works

```
sam local start-api
```


Create a venv and install requirements.txt

```
python -m venv create aws-demo
pip install -r requirements.txt
```


Install boto3 and refresh requirements.txt

```
pip install boto3
pip freeze > requirements.txt
```


Create Place Index in template.yml

```
  MyPlaceIndex:
    Type: AWS::Location::PlaceIndex
    Properties:
      DataSource: Esri
      IndexName: my-place-index
```



Python code to query the index:

```
import boto3
client = boto3.client('location')

client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')

place_id = client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')['Results'][0]['PlaceId']

client.get_place(PlaceId=place_id, IndexName='my-place-index')
```


app.py code for suggestions:


```
import json
import boto3


def suggestions(event, context):
    client = boto3.client('location')
    res = client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')

    return {
        "statusCode": 200,
        "body": res["Results"]
    }

```


---

Fix permissions by adding the following "Policies" block to the function's Properties:

```
      Policies:
        - Statement:
            - Sid: CreateLogs
              Effect: Allow
              Action:
                - "logs:CreateLogGroup"
                - "logs:CreateLogStream"
                - "logs:PutLogEvents"
              Resource: "*"
            - Sid: QueryPlaceIndex
              Effect: Allow
              Action:
                - "geo:SearchPlaceIndexForSuggestions"
              Resource: !GetAtt MyPlaceIndex.Arn # Reference the ARN of the PlaceIndex resource
```


Use the query parameter (app.py):

```
import json
import boto3

def suggestions(event, context):
    client = boto3.client('location')
    q = event["queryStringParameters"]["q"]
    res = client.search_place_index_for_suggestions(Text=q, IndexName='my-place-index')

    return {
        "statusCode": 200,
        "body": json.dumps(res["Results"])
    }

```

If you want you can filter results for specific countries:

```
res = client.search_place_index_for_suggestions(Text=q, IndexName='my-place-index', FilterCountries=['ISR'])
```




# Commands used in part 2

Modify the event to handle all paths and methods:

```
Events:
  Anything:
    Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
    Properties:
      Path: /{all+}
      Method: ANY
```

Install modules:

```
pip install flask flask-lambda
pip freeze > location_api/requirements.txt
```


Correct requirements.txt

```
boto3==1.26.82
botocore==1.29.84
certifi==2022.12.7
charset-normalizer==3.0.1
click==8.1.3
flask-lambda==0.0.4
Werkzeug==2.0.3
idna==3.4
itsdangerous==2.1.2
Jinja2==3.1.2
jmespath==1.0.1
MarkupSafe==2.1.2
python-dateutil==2.8.2
requests==2.28.2
s3transfer==0.6.0
six==1.16.0
urllib3==1.26.14
```


Flask code in app.py


```
from flask import jsonify, request
from flask_lambda import FlaskLambda
import boto3

app = FlaskLambda(__name__)

@app.route('/suggestions')
def suggestions():
    client = boto3.client('location')
    q = request.args.get('q')    
    res = client.search_place_index_for_suggestions(Text=q, IndexName='my-place-index', FilterCountries=['ISR'])
    print(jsonify(res["Results"]))
    return jsonify(res["Results"])

@app.route('/hello')
def hello():
    return jsonify("hello world")

@app.route('/<path:path>')
def catch_all(path):
    # handle all other request paths
    return f'Path not found: {path}', 404
```

Fix handler in template.yml

```
Handler: app.app
```


Deploy and fix permissions


```
- Sid: QueryPlaceIndex
  Effect: Allow
  Action:
    - "geo:SearchPlaceIndexForSuggestions"
    - "geo:GetPlace"
  Resource: !GetAtt MyPlaceIndex.Arn # Reference the ARN of the PlaceIndex resource
```

