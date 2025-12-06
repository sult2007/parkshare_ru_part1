import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConversationList } from '@/components/chat/conversation-list';
import type { Conversation } from '@/components/chat/types';

describe('ConversationList', () => {
  const baseConversations: Conversation[] = [
    {
      id: 'one',
      title: 'First thread',
      updatedAt: Date.now() - 1000 * 60 * 5,
      messages: [{ id: 'm1', role: 'user', content: 'Hello', createdAt: Date.now() - 1000 * 60 * 5 }]
    },
    {
      id: 'two',
      title: 'Second thread',
      updatedAt: Date.now() - 1000 * 60 * 60,
      messages: [{ id: 'm2', role: 'assistant', content: 'Hi there', createdAt: Date.now() - 1000 * 60 * 60 }]
    }
  ];

  beforeEach(() => {
    jest.spyOn(window, 'prompt').mockReturnValue('Renamed thread');
    jest.spyOn(window, 'confirm').mockReturnValue(true);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders conversations and handles selection, rename, and deletion', async () => {
    const onSelect = jest.fn();
    const onCreate = jest.fn();
    const onRename = jest.fn();
    const onDelete = jest.fn();

    render(
      <ConversationList
        conversations={baseConversations}
        activeId={'one'}
        onSelect={onSelect}
        onCreate={onCreate}
        onRename={onRename}
        onDelete={onDelete}
      />
    );

    expect(screen.getByText('First thread')).toBeInTheDocument();
    expect(screen.getByText('Second thread')).toBeInTheDocument();

    await userEvent.click(screen.getByText('First thread'));
    expect(onSelect).toHaveBeenCalledWith('one');

    await userEvent.click(screen.getByText('New'));
    expect(onCreate).toHaveBeenCalled();

    const renameButton = screen.getAllByLabelText('Rename conversation')[0];
    await userEvent.click(renameButton);
    expect(onRename).toHaveBeenCalledWith('one', 'Renamed thread');

    const deleteButton = screen.getAllByLabelText('Delete conversation')[0];
    await userEvent.click(deleteButton);
    expect(onDelete).toHaveBeenCalledWith('one');
  });
});
