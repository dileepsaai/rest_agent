# WhatsApp SQL Agent Integration

This project integrates a SQL agent with WhatsApp using Twilio, allowing users to query their database through WhatsApp messages.

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Create a `.env` file with the following variables:
   ```
   # Database Configuration
   POSTGRES_DB=your_database_name
   POSTGRES_USER=your_database_user
   POSTGRES_PASSWORD=your_database_password
   POSTGRES_HOST=your_database_host
   POSTGRES_PORT=5432

   # Google API Configuration
   GOOGLE_API_KEY=your_google_api_key

   # Twilio Configuration
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   ```

3. **Twilio Setup**
   - Sign up for a Twilio account at https://www.twilio.com
   - Get your Account SID and Auth Token from the Twilio Console
   - Set up a WhatsApp Sandbox in your Twilio Console
   - Configure the webhook URL in your Twilio WhatsApp Sandbox settings to point to your server's `/webhook` endpoint

4. **Run the Application**
   ```bash
   python bot.py
   ```

5. **Expose Your Server**
   - Use ngrok or a similar tool to expose your local server:
   ```bash
   ngrok http 5000
   ```
   - Update your Twilio webhook URL with the ngrok URL

## Usage

1. Send a message to your Twilio WhatsApp number
2. Type your SQL query or natural language query
3. Receive the results directly in WhatsApp

Example queries:
- "Show me all users"
- "What are the top 5 products by sales?"
- "Add a new user with name John and email john@example.com"

## Security Considerations

- Keep your `.env` file secure and never commit it to version control
- Use HTTPS in production
- Implement rate limiting for the webhook endpoint
- Validate and sanitize incoming messages
- Use appropriate database user permissions

## Troubleshooting

- Check the Flask application logs for errors
- Verify your Twilio webhook URL is correctly configured
- Ensure all environment variables are properly set
- Check database connectivity


docker run -e "ACCEPT_EULA=Y" \
  -e "SA_PASSWORD=YourStrong@Passw0rd" \
  -p 1433:1433 \
  --name ms-sql \
  -d mcr.microsoft.com/mssql/server:2022-latest


docker cp init-ms.sql ms-sql:/init.sql

docker run -it --rm \
  --network container:ms-sql \
  -v $(pwd)/init-ms.sql:/tmp/init.sql \
  mcr.microsoft.com/mssql-tools \
  /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'YourStrong@Passw0rd' -i /tmp/init.sql
