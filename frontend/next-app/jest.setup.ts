import '@testing-library/jest-dom';

const { TextEncoder, TextDecoder } = require('util');
if (!global.TextEncoder) {
  global.TextEncoder = TextEncoder;
}
if (!global.TextDecoder) {
  global.TextDecoder = TextDecoder;
}

if (!global.crypto) {
  const { webcrypto } = require('crypto');
  global.crypto = webcrypto as Crypto;
}

if (!global.ReadableStream) {
  const { ReadableStream } = require('stream/web');
  global.ReadableStream = ReadableStream as typeof global.ReadableStream;
}

if (!global.fetch || !global.Response) {
  const { fetch, Headers, Request, Response } = require('undici');
  if (!global.fetch) {
    global.fetch = fetch;
  }
  if (!global.Headers) {
    global.Headers = Headers;
  }
  if (!global.Request) {
    global.Request = Request;
  }
  if (!global.Response) {
    global.Response = Response;
  }
}
