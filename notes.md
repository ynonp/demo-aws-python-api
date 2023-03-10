# General AWS commands

get account id:

```
aws sts get-caller-identity --query "Account" --output text
```

# Part 1 - create a lambda for "suggestions"

```
sam init --runtime python3.9 --name location-demo
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

Now let's play with the location service. First we'll need a place index. Let's modify template.yml to create one. Modify template.yml and add the resource block (in Resources):

```
  MyPlaceIndex:
    Type: AWS::Location::PlaceIndex
    Properties:
      DataSource: Esri
      IndexName: my-place-index
```

Enter LocationService panel and verify index was created.

Now let's use the index from an interactive python REPL:

```
import boto3
client = boto3.client('location')

client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')

place_id = client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')['Results'][0]['PlaceId']

client.get_place(PlaceId=place_id, IndexName='my-place-index')
```

Finally let's modify the function code to return the list of suggestions. Modify app.py to:

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

Since I changed the name of the function, change also in `template.yml` the Handler line and the path, resulting in the following HelloWorldFunction resource:

```
  HelloWorldFunction:
    Type: AWS::Serverless::Function # More info about Function Resource: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#awsserverlessfunction
    Properties:
      CodeUri: hello_world/
      Handler: app.suggestions
      Runtime: python3.9
      Architectures:
        - x86_64
      Events:
        HelloWorld:
          Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
          Properties:
            Path: /hello
            Method: get
```

start the local server and check if everything works

```
sam local start-api
```

It won't but the reason is interesting. In fact `requirements.txt` was not installed, and sam uses an old version of boto3.

To fix it we need to run `sam build` from another terminal. Unfortunately after running `sam build` we need to re-run it every time we change the code (they have an open bug about it here [https://github.com/aws/aws-sam-cli/issues/921](https://github.com/aws/aws-sam-cli/issues/921)).

Open another terminal for builds and run:

```
sam build
```

Keep the terminal open so you can re-run build after every code change. The bright side is that it works and the method returned a list of suggestions (texts + place ids)

Let's deploy:

```
sam deploy --guided
```

Access the function on AWS to see if it works. It doesn't. Check the logs to see the permission error:

```
[ERROR] AccessDeniedException: An error occurred (AccessDeniedException) when calling the SearchPlaceIndexForSuggestions operation: User: arn:aws:sts::986797509163:assumed-role/location-demo-HelloWorldFunctionRole-FNEIG3JHHWUC/location-demo-HelloWorldFunction-l4w7rhfwXc0p is not authorized to perform: geo:SearchPlaceIndexForSuggestions on resource: arn:aws:geo:us-east-1:986797509163:place-index/my-place-index
Traceback (most recent call last):
  File "/var/task/app.py", line 7, in suggestions
    res = client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')
  File "/var/runtime/botocore/client.py", line 391, in _api_call
    return self._make_api_call(operation_name, kwargs)
  File "/var/runtime/botocore/client.py", line 719, in _make_api_call
    raise error_class(parsed_response, operation_name)
[ERROR] AccessDeniedException: An error occurred (AccessDeniedException) when calling the SearchPlaceIndexForSuggestions operation: User: arn:aws:sts::986797509163:assumed-role/location-demo-HelloWorldFunctionRole-FNEIG3JHHWUC/location-demo-HelloWorldFunction-l4w7rhfwXc0p is not authorized to perform: geo:SearchPlaceIndexForSuggestions on resource: arn:aws:geo:us-east-1:986797509163:place-index/my-place-index Traceback (most recent call last):   File "/var/task/app.py", line 7, in suggestions     res = client.search_place_index_for_suggestions(Text='אוני', IndexName='my-place-index')   File "/var/runtime/botocore/client.py", line 391, in _api_call     return self._make_api_call(operation_name, kwargs)   File "/var/runtime/botocore/client.py", line 719, in _make_api_call     raise error_class(parsed_response, operation_name)
```

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

Deploy again and verify this time the code works

---

Finally let's get the text from a query parameter. Modify the code to the following version:

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

The variable event["queryStringParameters"] includes a dictionary of all query string parameters. Using the parameter name "q" we can search according to the provided text.

After a few searches you'll notice the results are from all over the world. We can focus the search on results from a specific country by adding a FilterCountries parameter to the API call:

```
import json
import boto3

def suggestions(event, context):
    client = boto3.client('location')
    q = event["queryStringParameters"]["q"]
    res = client.search_place_index_for_suggestions(Text=q, IndexName='my-place-index', FilterCountries=['ISR'])

    return {
        "statusCode": 200,
        "body": json.dumps(res["Results"])
    }
```

Deploy the final version and take a break.

---

# Part 2 - Add a second Endpoint to get place info
In order to add a new endpoint we have 2 options:

1. We can create one endpoint that would handle ALL incoming requests,
   and inside the function use the event data to call the correct handler

2. We can register a different handler function per endpoint.

With the first approach we only need to define the permissions once, and we have more control in our code over the routing flow. with the second approach we get more fine grained control over the capabilities of each handler function. For this example I'll use the first approach.

Modify the Events block so our function will receive all incoming HTTP calls:

```
Events:
  Anything:
    Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
    Properties:
      Path: /{all+}
      Method: ANY
```

Notice how the path /{all+} catch anything that is of the format '/...'. If we also want to handle the root path (simply `/`) we need to specify that explicitly.

This would also be a good time to rename the function to MyLocationAPI.


Now let's modify our python code to use flask so we'll have better control over the routing.
First install flask, flask-lambda and fix requirements.txt:

```
pip install flask flask-lambda
pip freeze > location_api/requirements.txt
```

flask-lambda is a connection library that makes Flask compatible with AWS Lambda

HOWEVER ...

flask-lambda is not up-to-date with the latest flask, and so the naive approach won't work. We'll use the following requirements.txt file to install the latest working versions:

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

Change the code in app.py to the following:

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

And finally in template.yml we'll want to use the global `app.app` varaible, instead of the `app.suggestions` function, so let's fix it:

```
Timeout: 10
Handler: app.app
Runtime: python3.9
Architectures:
  - x86_64
Events:
  ApiCall:
    Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
    Properties:
      Path: /{all+}
      Method: ANY
```

While we're at it don't forget to delete unused references to HelloWorldFunction in the output block (at the end of the template.yml file). This is what the output block should look like:

```
Outputs:
  MyLocationAPIFunction:
    Description: "Hello World Lambda Function ARN"
    Value: !GetAtt MyLocationAPI.Arn

  MyLocationAPI:
    Description: "API Gateway endpoint URL for Prod stage for Hello World function"
    Value: !Sub "https://${ServerlessRestApi}.execute-api.${AWS::Region}.amazonaws.com/Prod/"
```


We're finally ready to play with the code:

1. Browse to `localhost:3000/hello` and see the `hello world` message from `/hello` route.

2. Browse to `localhost:3000/suggestions?q=tel` and see some places around Tel Aviv from `/suggestions` route.

Now let's add our second (actually third, because we have `/hello`) endpoint. Add the following code to `app.py`:

```
@app.route('/place')
def place():
    place_id = request.args.get('id')
    res = client.get_place(IndexName='my-place-index', PlaceId=place_id)
    return jsonify(res["Place"])
```

The function uses another AWS endpoint to get information about a specific place. In the next part we'll use this API to show the place on a map.

Last task before we finish is of course to deploy all our work to AWS and see that it also works there. Let's use sam:

```
sam deploy --guided
```

Checking the API we can see that `suggestions` worked and also `hello`, but `place` did not. Do you have an idea why?

Right - it was missing permissions issue. We can verify in the log but we actually don't need to. Look again at the permissions our function has:

```
            - Sid: QueryPlaceIndex
              Effect: Allow
              Action:
                - "geo:SearchPlaceIndexForSuggestions"
              Resource: !GetAtt MyPlaceIndex.Arn # Reference the ARN of the PlaceIndex resource
```


We need to add the new action `geo:GetPlace`. Let's add it and deploy again:

```
- Sid: QueryPlaceIndex
  Effect: Allow
  Action:
    - "geo:SearchPlaceIndexForSuggestions"
    - "geo:GetPlace"
  Resource: !GetAtt MyPlaceIndex.Arn # Reference the ARN of the PlaceIndex resource
```

Verify that you can get Place info and take another break. You deserve it.

---







