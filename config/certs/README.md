

## Naming Conventions

- **Root Certificate**: `root-CA.crt`
  - This is the root certificate used to verify the authenticity of the server certificates.

- **Server Certificate**: `verdure.cert.pem`
  - This certificate is used by the server to establish a secure connection.

- **Private Key**: `verdure.private.key`
  - The private key associated with the server certificate. Keep this file secure and do not share it.

- **Public Key**: `verdure.public.key`
  - The public key that corresponds to the private key. This can be shared with clients to encrypt data sent to the server.

> Make sure to follow the naming conventions to ensure that the server can find the necessary files because I have hard-coded the file names in the server code.