/**
 * Test component demonstrating API client usage.
 *
 * This component shows how to use the API hooks to interact with the backend.
 * It can be imported and used in any component to test the API client.
 *
 * Example usage:
 * ```tsx
 * import TestApiClient from './TestApiClient'
 *
 * function App() {
 *   return <TestApiClient />
 * }
 * ```
 */

import { useInventoryList } from './api';

function TestApiClient() {
  // Test the inventory list hook
  const { data, isLoading, error } = useInventoryList({
    limit: 10,
    category: 'produce',
  });

  if (isLoading) {
    return <div>Loading inventory...</div>;
  }

  if (error) {
    return <div>Error: {error.message}</div>;
  }

  return (
    <div>
      <h2>Inventory Items</h2>
      {data && data.length > 0 ? (
        <ul>
          {data.map((item) => (
            <li key={item.id}>
              {item.name} - {item.quantity} {item.unit}
            </li>
          ))}
        </ul>
      ) : (
        <p>No items found</p>
      )}
    </div>
  );
}

export default TestApiClient;
