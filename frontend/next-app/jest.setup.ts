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
